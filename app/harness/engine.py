"""Harness 引擎 — Agent 的「身体」

职责：
1. 消息路由（简单/普通/复杂 → 不同处理路径）
2. 三层 Prompt 组装（静态/动态/临时）
3. AutoCompact（上下文压缩）
4. 意识流日志（决策追踪）
5. 错误恢复（超时重试、人设重注入）

设计原则（参考 Claude Code Harness）：
- Harness 永远在线，Agent 内核可热替换
- Agent 崩溃后 Harness 自动恢复
- 人设文件更新后可热加载，不重启服务
"""

import time
import logging
from dataclasses import dataclass

from app.config import settings
from app.services import memory
from app.services.agent import ask_claude
from app.skills.router import match_skill
from app.harness.prompt_builder import PromptBuilder
from app.harness.auto_compact import (
    should_compact, build_compact_prompt, compact_messages, KEEP_RECENT_ROUNDS,
)
from app.harness.consciousness import ConsciousnessStream
from app.harness.status_monitor import StatusMonitor

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    """消息处理结果"""
    response: str
    skill_used: str
    duration_ms: int
    compacted: bool = False


class HarnessEngine:
    """Harness 引擎 — 编排 Agent 的所有行为"""

    def __init__(self):
        self.prompt_builder = PromptBuilder(settings.workspace_dir)
        self.consciousness = ConsciousnessStream(
            log_dir=f"{settings.data_dir}/consciousness"
        )
        self.status_monitor = StatusMonitor(self.consciousness)
        # 每用户的压缩摘要缓存
        self._compact_summaries: dict[str, str] = {}

    async def process_message(
        self,
        user_id: str,
        content: str,
        message_context: dict | None = None,
    ) -> ProcessResult:
        """处理一条用户消息 — Harness 的核心方法

        流程：
        1. 获取用户上下文
        2. 检查是否需要 AutoCompact
        3. 构建三层 Prompt
        4. 意图路由
        5. 调用 Agent 内核
        6. 记录意识流
        7. 错误恢复
        """
        start_time = time.time()

        # 1. 获取用户上下文
        user_context = memory.get_user_context(user_id)

        # 2. AutoCompact 检查
        conversation_summary = self._compact_summaries.get(user_id, "")
        all_messages = memory.get_recent_messages(user_id, limit=200)
        compacted = False

        if should_compact(all_messages):
            conversation_summary = await self._run_compact(user_id, all_messages)
            compacted = True

        # 3. 意图路由
        skill = match_skill(content)

        # 4. 构建三层 Prompt
        prompt_layers = self.prompt_builder.build(
            user_context=user_context,
            skill_prompt=skill.prompt,
            conversation_summary=conversation_summary,
        )
        system_prompt = prompt_layers.build_system_prompt()

        # 5. 调用 Agent 内核（带错误恢复）
        response = await self._call_agent_with_recovery(
            prompt=content,
            system_prompt=system_prompt,
            use_plan=skill.use_plan,
            user_id=user_id,
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # 6. 记录意识流
        self.consciousness.log_message(
            user_id=user_id,
            thought=f"收到消息: {content[:50]}... → 技能: {skill.name} → 回复: {response[:50]}...",
            skill=skill.name,
            duration_ms=duration_ms,
        )

        # 7. 记录状态快照（MCP 工具调用统计）
        self.status_monitor.log_status_snapshot(user_id)

        return ProcessResult(
            response=response,
            skill_used=skill.name,
            duration_ms=duration_ms,
            compacted=compacted,
        )

    async def _run_compact(self, user_id: str, messages: list[dict]) -> str:
        """执行 AutoCompact 压缩"""
        logger.info("AutoCompact triggered for user %s (%d messages)", user_id, len(messages))

        compact_prompt = build_compact_prompt(messages, KEEP_RECENT_ROUNDS)
        if not compact_prompt:
            return self._compact_summaries.get(user_id, "")

        # 用 Claude 生成交接摘要
        summary = await ask_claude(
            prompt=compact_prompt,
            system_prompt="你是一个对话摘要助手。请生成简洁的交接摘要，保留关键信息。",
        )

        # 缓存摘要
        self._compact_summaries[user_id] = summary

        # 记录
        result = compact_messages(messages, summary, KEEP_RECENT_ROUNDS)
        self.consciousness.log_compact(user_id, result.compacted_count, len(summary))

        return summary

    async def _call_agent_with_recovery(
        self,
        prompt: str,
        system_prompt: str,
        use_plan: bool,
        user_id: str,
        max_retries: int = 2,
    ) -> str:
        """调用 Agent 内核，带错误恢复

        恢复策略：
        - 第 1 次失败：重试（可能是网络抖动）
        - 第 2 次失败：简化 prompt 重试（减少 token）
        - 都失败：返回友好错误消息
        """
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                current_prompt = prompt
                current_system = system_prompt

                # 第 2 次重试：简化 system prompt（去掉 Layer 3 技能指令）
                if attempt == 2:
                    # 退化到只用 Layer 1 + Layer 2
                    current_system = self.prompt_builder.build(
                        user_context=memory.get_user_context(user_id),
                    ).build_system_prompt()
                    self.consciousness.log_error(
                        user_id, "Retry with simplified prompt", "Stripped skill prompt"
                    )

                response = await ask_claude(
                    prompt=current_prompt,
                    system_prompt=current_system,
                    use_plan=use_plan,
                )
                return response

            except Exception as e:
                last_error = e
                logger.warning(
                    "Agent call failed (attempt %d/%d) for user %s: %s",
                    attempt + 1, max_retries + 1, user_id, str(e),
                )
                self.consciousness.log_error(
                    user_id,
                    f"Agent call failed: {str(e)}",
                    f"Attempt {attempt + 1}/{max_retries + 1}",
                )

        # 所有重试都失败
        logger.error("All retries exhausted for user %s: %s", user_id, str(last_error))
        return "妹妹这边出了点小状况，你稍等一下再问我哈"

    def reload_persona(self):
        """热加载人设文件（不重启服务）"""
        self.prompt_builder.invalidate_cache()
        logger.info("Persona files reloaded")


# 全局 Harness 实例
harness = HarnessEngine()

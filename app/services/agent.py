"""Claude Code 交互层 — Agent 内核（纯 LLM 调用，不含业务逻辑）

Harness 架构下的职责划分：
- agent.py（本文件）：只负责调用 Claude CLI，是最薄的一层
- harness/engine.py：负责 Prompt 组装、上下文管理、错误恢复
- harness/prompt_builder.py：负责三层 Prompt 构建

设计原则："Agent 内核可热替换"
- 未来换模型（Claude → 其他）只需改这个文件
- Harness 层完全不受影响
"""

import asyncio
import logging
from app.config import settings

logger = logging.getLogger(__name__)


async def ask_claude(
    prompt: str,
    system_prompt: str = "",
    user_context: str = "",
    skill_hint: str = "",
    use_plan: bool = False,
) -> str:
    """调用 Claude Code CLI 处理消息

    Args:
        prompt: 用户消息
        system_prompt: 完整的 system prompt（由 Harness 层组装）
        user_context: [兼容旧调用] 用户上下文
        skill_hint: [兼容旧调用] 技能提示
        use_plan: 是否使用 plan 模式

    Returns:
        Claude 的纯文本回复
    """
    # 兼容旧调用方式（直接传 user_context + skill_hint）
    if not system_prompt and (user_context or skill_hint):
        system_prompt = _build_legacy_prompt(user_context, skill_hint)

    # 构建 Claude CLI 命令
    cmd = [
        "claude",
        "--print",           # 直接输出结果，不进入交互模式
        "--no-input",        # 不等待用户输入
        "--output-format", "text",
        "--max-turns", "5" if use_plan else "3",
    ]

    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])

    # plan 模式：复杂任务先规划再执行
    if use_plan:
        cmd.insert(1, "--plan")

    cmd.append(prompt)

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=settings.workspace_dir,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=settings.claude_timeout,
        )

        if process.returncode != 0:
            error_msg = stderr.decode().strip()
            logger.error("Claude CLI error (code=%d): %s", process.returncode, error_msg)
            raise RuntimeError(f"Claude CLI error: {error_msg}")

        response = stdout.decode().strip()
        if not response:
            return "妹妹没听清，你再说一次？"

        return response

    except asyncio.TimeoutError:
        logger.error("Claude CLI timeout after %ds", settings.claude_timeout)
        raise
    except FileNotFoundError:
        logger.error("Claude CLI not found, please install: npm i -g @anthropic-ai/claude-code")
        raise


def _build_legacy_prompt(user_context: str, skill_hint: str) -> str:
    """兼容旧调用方式 — 从 workspace 读取人设文件拼装 prompt

    注意：新代码应使用 Harness 层的 PromptBuilder，不走这里。
    """
    import os

    system_parts = []

    soul_path = f"{settings.workspace_dir}/SOUL.md"
    claude_md_path = f"{settings.workspace_dir}/CLAUDE.md"

    try:
        with open(soul_path, "r") as f:
            system_parts.append(f.read())
    except FileNotFoundError:
        logger.warning("SOUL.md not found at %s", soul_path)

    try:
        with open(claude_md_path, "r") as f:
            system_parts.append(f.read())
    except FileNotFoundError:
        logger.warning("CLAUDE.md not found at %s", claude_md_path)

    if user_context:
        system_parts.append(f"\n---\n当前用户上下文：\n{user_context}")

    if skill_hint:
        system_parts.append(f"\n---\n请使用以下技能处理本次请求：\n{skill_hint}")

    return "\n\n".join(system_parts)

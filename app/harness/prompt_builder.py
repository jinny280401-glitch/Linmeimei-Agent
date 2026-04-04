"""三层 Prompt 构建器 — 参考 Claude Code 的 DYNAMIC_BOUNDARY 设计

Layer 1 (静态): 人设核心指令 — 跨会话缓存，极少变更
Layer 2 (动态): 用户档案 + 当前状态 — 每轮更新
Layer 3 (临时): 当前消息 + 技能提示 — 每次调用

设计原则：
- 每一行都必须通过铁律检验："删了会出错吗？如果不会，就砍掉"
- Layer 1 压缩后必须重注入（防止人设崩塌）
- Layer 2 动态段与 Layer 1 之间有明确边界标记
"""

import os
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PromptLayers:
    """三层 Prompt 结构"""
    layer1_static: str      # 人设核心（SOUL.md + CLAUDE.md）
    layer2_dynamic: str     # 用户档案 + 对话摘要
    layer3_ephemeral: str   # 当前消息 + 技能提示

    def build_system_prompt(self) -> str:
        """组装完整 system prompt，带边界标记"""
        parts = []

        # Layer 1: 静态人设（可缓存）
        if self.layer1_static:
            parts.append(self.layer1_static)

        # 动态边界标记（参考 Claude Code 的 DYNAMIC_BOUNDARY）
        parts.append("\n--- DYNAMIC_BOUNDARY（以下内容每轮更新）---\n")

        # Layer 2: 动态用户上下文
        if self.layer2_dynamic:
            parts.append(self.layer2_dynamic)

        # Layer 3: 临时技能提示
        if self.layer3_ephemeral:
            parts.append(f"\n---\n{self.layer3_ephemeral}")

        return "\n\n".join(parts)

    @property
    def static_token_estimate(self) -> int:
        """估算静态层 token 数（粗略：1 中文字 ≈ 2 token）"""
        return len(self.layer1_static) * 2

    @property
    def total_token_estimate(self) -> int:
        """估算总 token 数"""
        total_chars = len(self.layer1_static) + len(self.layer2_dynamic) + len(self.layer3_ephemeral)
        return total_chars * 2


class PromptBuilder:
    """Prompt 构建器 — 从文件和上下文组装三层 Prompt"""

    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        # 启动时加载 Layer 1（不变，缓存住）
        self._layer1_cache: str | None = None

    def get_layer1(self) -> str:
        """Layer 1: 静态人设 — 跨会话缓存

        加载顺序：SOUL.md → workspace/CLAUDE.md
        这些文件极少变更，启动后缓存住。
        """
        if self._layer1_cache is not None:
            return self._layer1_cache

        parts = []

        # SOUL.md: 核心人格定义
        soul_path = os.path.join(self.workspace_dir, "SOUL.md")
        soul = self._read_file(soul_path)
        if soul:
            parts.append(soul)

        # CLAUDE.md: 执行指令
        claude_path = os.path.join(self.workspace_dir, "CLAUDE.md")
        claude = self._read_file(claude_path)
        if claude:
            parts.append(claude)

        self._layer1_cache = "\n\n".join(parts)
        return self._layer1_cache

    def build_layer2(
        self,
        user_context: str,
        conversation_summary: str = "",
    ) -> str:
        """Layer 2: 动态用户上下文 — 每轮更新

        包含：用户档案 + 对话摘要（来自 AutoCompact）
        """
        parts = []

        if user_context:
            parts.append(f"当前用户上下文：\n{user_context}")

        if conversation_summary:
            parts.append(f"对话摘要（早期对话压缩）：\n{conversation_summary}")

        return "\n\n".join(parts)

    def build_layer3(
        self,
        skill_prompt: str = "",
    ) -> str:
        """Layer 3: 临时提示 — 每次调用

        包含：技能指令（如果匹配到了技能）
        """
        if skill_prompt:
            return f"请使用以下技能处理本次请求：\n{skill_prompt}"
        return ""

    def build(
        self,
        user_context: str,
        skill_prompt: str = "",
        conversation_summary: str = "",
    ) -> PromptLayers:
        """构建完整的三层 Prompt"""
        return PromptLayers(
            layer1_static=self.get_layer1(),
            layer2_dynamic=self.build_layer2(user_context, conversation_summary),
            layer3_ephemeral=self.build_layer3(skill_prompt),
        )

    def invalidate_cache(self):
        """人设文件更新后，清除 Layer 1 缓存（支持热更新）"""
        self._layer1_cache = None
        logger.info("Layer 1 prompt cache invalidated")

    def _read_file(self, path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            logger.warning("Prompt file not found: %s", path)
            return ""

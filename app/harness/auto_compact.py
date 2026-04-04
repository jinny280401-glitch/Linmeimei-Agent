"""AutoCompact — 上下文压缩系统

参考 Claude Code 的压缩策略：
- 触发条件：对话轮次超过阈值（林妹妹场景：30 轮）
- 压缩策略：LLM 生成交接摘要，保留最近 N 轮原文
- 关键：压缩后必须重注入人设 prompt，防止"出戏"

与 Claude Code 的区别：
- Claude Code 按 token 85% 触发
- 林妹妹按轮次触发（更简单可靠，妈妈场景对话密度低）
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 压缩配置
COMPACT_THRESHOLD = 30       # 超过 30 轮触发压缩
KEEP_RECENT_ROUNDS = 8       # 保留最近 8 轮原文（16 条消息）
SUMMARY_MAX_CHARS = 500      # 摘要最大字符数


@dataclass
class CompactResult:
    """压缩结果"""
    summary: str                    # 交接摘要
    recent_messages: list[dict]     # 保留的最近消息
    compacted_count: int            # 被压缩的消息数
    needs_compact: bool             # 是否触发了压缩


def should_compact(messages: list[dict]) -> bool:
    """判断是否需要压缩"""
    rounds = len(messages) // 2  # 一问一答 = 一轮
    return rounds >= COMPACT_THRESHOLD


def build_compact_prompt(messages: list[dict], keep_recent: int = KEEP_RECENT_ROUNDS) -> str:
    """构建压缩请求的 prompt — 让 LLM 生成交接摘要

    这个 prompt 会发送给 Claude，让它生成一段摘要来替代旧对话。
    """
    # 需要被压缩的旧消息
    keep_count = keep_recent * 2  # 每轮 2 条
    old_messages = messages[:-keep_count] if keep_count < len(messages) else []

    if not old_messages:
        return ""

    # 组装对话文本
    conversation_text = "\n".join(
        f"{'用户' if m['role'] == 'user' else '林妹妹'}: {m['content']}"
        for m in old_messages
    )

    return f"""请为以下对话生成一段简洁的「交接摘要」，用于保持对话连续性。

要求：
1. 用第三人称描述（"用户提到了..."、"讨论了..."）
2. 保留关键信息：用户的情绪变化、重要事件、未完成话题
3. 不要逐条复述，要压缩为结构化摘要
4. 控制在 {SUMMARY_MAX_CHARS} 字以内
5. 格式：
   - 话题：...
   - 用户情绪：...
   - 关键事件：...
   - 待跟进：...

对话记录：
{conversation_text}"""


def compact_messages(
    messages: list[dict],
    summary: str,
    keep_recent: int = KEEP_RECENT_ROUNDS,
) -> CompactResult:
    """执行压缩：用摘要替代旧消息

    Args:
        messages: 全部消息列表
        summary: LLM 生成的交接摘要
        keep_recent: 保留最近多少轮
    """
    keep_count = keep_recent * 2
    recent = messages[-keep_count:] if keep_count < len(messages) else messages
    compacted = len(messages) - len(recent)

    logger.info(
        "AutoCompact: compressed %d messages into summary (%d chars), kept %d recent",
        compacted, len(summary), len(recent),
    )

    return CompactResult(
        summary=summary,
        recent_messages=recent,
        compacted_count=compacted,
        needs_compact=True,
    )

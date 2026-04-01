"""Claude Code 交互层 — 通过 subprocess 调用 Claude CLI"""

import asyncio
import json
import logging
from app.config import settings

logger = logging.getLogger(__name__)


async def ask_claude(
    prompt: str,
    user_context: str = "",
    skill_hint: str = "",
    use_plan: bool = False,
) -> str:
    """调用 Claude Code CLI 处理消息

    Args:
        prompt: 用户消息
        user_context: 用户上下文（记忆摘要）
        skill_hint: 技能提示（告诉 Claude 使用哪个 skill）
        use_plan: 是否使用 plan 模式（复杂任务先规划再执行）

    Returns:
        Claude 的纯文本回复
    """
    # 组装系统提示
    system_parts = []

    # 读取人设文件
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

    # 注入用户上下文
    if user_context:
        system_parts.append(f"\n---\n当前用户上下文：\n{user_context}")

    # 注入技能提示
    if skill_hint:
        system_parts.append(f"\n---\n请使用以下技能处理本次请求：\n{skill_hint}")

    system_prompt = "\n\n".join(system_parts)

    # 构建 Claude CLI 命令
    cmd = [
        "claude",
        "--print",           # 直接输出结果，不进入交互模式
        "--no-input",        # 不等待用户输入
        "--output-format", "text",
        "--system-prompt", system_prompt,
        "--max-turns", "5" if use_plan else "3",
        prompt,
    ]

    # plan 模式：复杂任务（投研分析、客户沙盘等）先规划再执行
    if use_plan:
        cmd.insert(1, "--plan")

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
            logger.error("Claude CLI error: %s", error_msg)
            return "妹妹这边出了点小状况，你稍等一下再问我哈"

        response = stdout.decode().strip()
        if not response:
            return "妹妹没听清，你再说一次？"

        return response

    except asyncio.TimeoutError:
        logger.error("Claude CLI timeout after %ds", settings.claude_timeout)
        return "这个问题比较复杂，妹妹需要多想一会儿，你稍后再问我"
    except FileNotFoundError:
        logger.error("Claude CLI not found, please install: npm i -g @anthropic-ai/claude-code")
        return "妹妹这边出了点小状况，你稍等一下再问我哈"

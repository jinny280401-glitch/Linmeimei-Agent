"""飞书事件处理 — 接收消息、处理、回复"""

import json
import hashlib
import logging
from datetime import datetime
from fastapi import APIRouter, Request, BackgroundTasks
from app.models.schemas import IncomingMessage, UserProfile
from app.services import memory, feishu_client
from app.services.agent import ask_claude
from app.skills.router import match_skill

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feishu", tags=["feishu"])

# 消息去重缓存（防止飞书重发）
_processed_messages: set[str] = set()
_MAX_CACHE_SIZE = 1000


@router.post("/event")
async def handle_event(request: Request, background_tasks: BackgroundTasks):
    """飞书事件回调入口"""
    body = await request.json()

    # 飞书 URL 验证（首次配置时）
    if "challenge" in body:
        return {"challenge": body["challenge"]}

    # 事件 v2.0 格式
    header = body.get("header", {})
    event = body.get("event", {})

    # 验证事件类型
    event_type = header.get("event_type", "")
    if event_type != "im.message.receive_v1":
        return {"code": 0}

    # 提取消息信息
    message_data = event.get("message", {})
    sender = event.get("sender", {})

    message_id = message_data.get("message_id", "")

    # 消息去重
    if message_id in _processed_messages:
        return {"code": 0}
    _processed_messages.add(message_id)
    if len(_processed_messages) > _MAX_CACHE_SIZE:
        _processed_messages.clear()

    # 忽略非文本消息
    msg_type = message_data.get("message_type", "")
    if msg_type != "text":
        background_tasks.add_task(
            feishu_client.reply_message,
            message_id,
            "目前妹妹只能看文字消息哦，你用文字跟我说吧",
        )
        return {"code": 0}

    # 解析消息内容
    content_str = message_data.get("content", "{}")
    try:
        content_json = json.loads(content_str)
        text = content_json.get("text", "").strip()
    except json.JSONDecodeError:
        text = content_str.strip()

    if not text:
        return {"code": 0}

    # 群聊中去掉 @机器人 的部分
    chat_type = message_data.get("chat_type", "p2p")
    if chat_type == "group":
        mentions = message_data.get("mentions", [])
        for mention in mentions:
            mention_key = mention.get("key", "")
            text = text.replace(mention_key, "").strip()

    if not text:
        return {"code": 0}

    # 构建消息对象
    user_id = sender.get("sender_id", {}).get("open_id", "unknown")
    msg = IncomingMessage(
        user_id=user_id,
        user_name=sender.get("sender_id", {}).get("open_id", ""),
        chat_id=message_data.get("chat_id", ""),
        chat_type=chat_type,
        content=text,
        message_id=message_id,
    )

    # 异步处理消息（立即返回 200，避免飞书超时重发）
    background_tasks.add_task(_process_message, msg)
    return {"code": 0}


async def _process_message(msg: IncomingMessage) -> None:
    """处理消息的核心逻辑"""
    try:
        # 1. 检查是否新用户，获取用户上下文
        is_new = memory.is_new_user(msg.user_id)

        if is_new:
            # 新用户：获取飞书用户信息并创建画像
            user_info = await feishu_client.get_user_info(msg.user_id)
            profile = UserProfile(
                user_id=msg.user_id,
                user_name=user_info.get("name", msg.user_name),
                first_seen=datetime.now().isoformat(),
                last_seen=datetime.now().isoformat(),
            )
            memory.save_user_profile(profile)

        # 更新 last_seen
        profile = memory.get_user_profile(msg.user_id)
        if profile:
            profile.last_seen = datetime.now().isoformat()
            memory.save_user_profile(profile)

        # 2. 保存用户消息
        memory.save_message(msg.user_id, "user", msg.content)

        # 3. 获取用户上下文
        user_context = memory.get_user_context(msg.user_id)

        # 4. 意图路由
        skill_name, skill_prompt = match_skill(msg.content)

        # 5. 调用 Claude
        response = await ask_claude(
            prompt=msg.content,
            user_context=user_context,
            skill_hint=skill_prompt,
        )

        # 6. 保存 Agent 回复
        memory.save_message(msg.user_id, "assistant", response, skill_used=skill_name)

        # 7. 回复飞书
        await feishu_client.reply_message(msg.message_id, response)

        logger.info(
            "Processed message from %s, skill=%s, response_len=%d",
            msg.user_id, skill_name, len(response),
        )

    except Exception:
        logger.exception("Error processing message from %s", msg.user_id)
        await feishu_client.reply_message(
            msg.message_id,
            "妹妹这边出了点小状况，你稍等一下再问我哈",
        )

"""企业微信事件处理 — 接收消息、处理、回复"""

import json
import hashlib
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from fastapi import APIRouter, Request, BackgroundTasks, Query
from app.models.schemas import IncomingMessage, UserProfile
from app.services import memory, wecom_client
from app.services.agent import ask_claude
from app.skills.router import match_skill
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/wecom", tags=["wecom"])

# 消息去重缓存（防止企业微信重发）
_processed_messages: set[str] = set()
_MAX_CACHE_SIZE = 1000


@router.get("/event")
async def verify_url(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
):
    """企业微信 URL 验证（首次配置时）"""
    # TODO: 实现消息解密验证
    # 企业微信要求对 echostr 进行解密后返回
    # 这里需要使用 wechatpy 库或自己实现 AES 解密
    logger.info("WeChat Work URL verification: signature=%s", msg_signature)
    return echostr


@router.post("/event")
async def handle_event(request: Request, background_tasks: BackgroundTasks):
    """企业微信事件回调入口"""
    # 企业微信使用 XML 格式
    body = await request.body()

    try:
        root = ET.fromstring(body.decode("utf-8"))
    except ET.ParseError:
        logger.error("Failed to parse XML: %s", body)
        return {"errcode": 0, "errmsg": "ok"}

    # 提取消息信息
    msg_type = root.find("MsgType")
    if msg_type is None or msg_type.text != "text":
        return {"errcode": 0, "errmsg": "ok"}

    # 提取关键字段
    from_user = root.find("FromUserName")
    content = root.find("Content")
    msg_id = root.find("MsgId")

    if from_user is None or content is None or msg_id is None:
        return {"errcode": 0, "errmsg": "ok"}

    message_id = msg_id.text
    user_id = from_user.text
    text = content.text.strip()

    if not text:
        return {"errcode": 0, "errmsg": "ok"}

    # 消息去重
    if message_id in _processed_messages:
        return {"errcode": 0, "errmsg": "ok"}
    _processed_messages.add(message_id)
    if len(_processed_messages) > _MAX_CACHE_SIZE:
        _processed_messages.clear()

    # 构建消息对象（添加渠道前缀）
    msg = IncomingMessage(
        user_id=f"wecom_{user_id}",  # 添加渠道前缀避免冲突
        user_name=user_id,
        chat_id=user_id,
        chat_type="p2p",
        content=text,
        message_id=message_id,
    )

    # 异步处理消息（立即返回，避免企业微信超时重发）
    background_tasks.add_task(_process_message, msg)
    return {"errcode": 0, "errmsg": "ok"}


async def _process_message(msg: IncomingMessage) -> None:
    """处理消息的核心逻辑（复用飞书的逻辑）"""
    try:
        # 提取真实的 external_userid（去掉 wecom_ 前缀）
        external_userid = msg.user_id.replace("wecom_", "")

        # 1. 检查是否新用户
        is_new = memory.is_new_user(msg.user_id)

        if is_new:
            # 新用户：创建画像
            profile = UserProfile(
                user_id=msg.user_id,
                user_name=msg.user_name,
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
        skill = match_skill(msg.content)

        # 5. 调用 Claude
        response = await ask_claude(
            prompt=msg.content,
            user_context=user_context,
            skill_hint=skill.prompt,
            use_plan=skill.use_plan,
        )

        # 6. 保存 Agent 回复
        memory.save_message(msg.user_id, "assistant", response, skill_used=skill.name)

        # 7. 回复企业微信
        await wecom_client.reply_message(external_userid, response)

        logger.info(
            "Processed WeChat Work message from %s, skill=%s, plan=%s, response_len=%d",
            msg.user_id, skill.name, skill.use_plan, len(response),
        )

    except Exception:
        logger.exception("Error processing WeChat Work message from %s", msg.user_id)
        # 提取真实的 external_userid
        external_userid = msg.user_id.replace("wecom_", "")
        await wecom_client.reply_message(
            external_userid,
            "妹妹这边出了点小状况，你稍等一下再问我哈",
        )

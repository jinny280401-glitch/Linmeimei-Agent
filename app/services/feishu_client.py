"""飞书 API 客户端 — 消息收发 + Token 管理"""

import time
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

# 飞书 API 基础地址
BASE_URL = "https://open.feishu.cn/open-apis"

# Token 缓存
_tenant_token = ""
_token_expires_at = 0


async def _get_tenant_token() -> str:
    """获取 tenant_access_token（自动缓存，过期前 5 分钟刷新）"""
    global _tenant_token, _token_expires_at

    if _tenant_token and time.time() < _token_expires_at - 300:
        return _tenant_token

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/auth/v3/tenant_access_token/internal",
            json={
                "app_id": settings.feishu_app_id,
                "app_secret": settings.feishu_app_secret,
            },
        )
        data = resp.json()

        if data.get("code") != 0:
            logger.error("Failed to get tenant token: %s", data)
            raise RuntimeError(f"飞书认证失败: {data.get('msg')}")

        _tenant_token = data["tenant_access_token"]
        _token_expires_at = time.time() + data.get("expire", 7200)
        logger.info("Tenant token refreshed, expires in %ds", data.get("expire", 7200))

    return _tenant_token


async def reply_message(message_id: str, text: str) -> bool:
    """回复飞书消息"""
    token = await _get_tenant_token()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/im/v1/messages/{message_id}/reply",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "content": f'{{"text": "{_escape_text(text)}"}}',
                "msg_type": "text",
            },
        )
        data = resp.json()

        if data.get("code") != 0:
            logger.error("Failed to reply message: %s", data)
            return False

    return True


async def send_message(chat_id: str, text: str) -> bool:
    """主动发送消息到会话"""
    token = await _get_tenant_token()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/im/v1/messages",
            headers={"Authorization": f"Bearer {token}"},
            params={"receive_id_type": "chat_id"},
            json={
                "receive_id": chat_id,
                "content": f'{{"text": "{_escape_text(text)}"}}',
                "msg_type": "text",
            },
        )
        data = resp.json()

        if data.get("code") != 0:
            logger.error("Failed to send message: %s", data)
            return False

    return True


async def get_user_info(user_id: str) -> dict:
    """获取用户信息"""
    token = await _get_tenant_token()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/contact/v3/users/{user_id}",
            headers={"Authorization": f"Bearer {token}"},
            params={"user_id_type": "open_id"},
        )
        data = resp.json()

        if data.get("code") == 0:
            user = data.get("data", {}).get("user", {})
            return {
                "name": user.get("name", ""),
                "open_id": user.get("open_id", ""),
            }

    return {"name": "", "open_id": user_id}


def _escape_text(text: str) -> str:
    """转义文本中的特殊字符"""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

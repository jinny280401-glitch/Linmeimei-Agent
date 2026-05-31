"""企业微信 API 客户端 — 消息收发 + Token 管理"""

import time
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

# 企业微信 API 基础地址
BASE_URL = "https://qyapi.weixin.qq.com/cgi-bin"

# Token 缓存
_access_token = ""
_token_expires_at = 0


async def _get_access_token() -> str:
    """获取 access_token（自动缓存，过期前 5 分钟刷新）"""
    global _access_token, _token_expires_at

    if _access_token and time.time() < _token_expires_at - 300:
        return _access_token

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/gettoken",
            params={
                "corpid": settings.wecom_corp_id,
                "corpsecret": settings.wecom_secret,
            },
        )
        data = resp.json()

        if data.get("errcode") != 0:
            logger.error("Failed to get access token: %s", data)
            raise RuntimeError(f"企业微信认证失败: {data.get('errmsg')}")

        _access_token = data["access_token"]
        _token_expires_at = time.time() + data.get("expires_in", 7200)
        logger.info("Access token refreshed, expires in %ds", data.get("expires_in", 7200))

    return _access_token


async def send_message(external_userid: str, text: str) -> bool:
    """主动发送消息给外部联系人"""
    token = await _get_access_token()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/message/send",
            params={"access_token": token},
            json={
                "touser": external_userid,
                "msgtype": "text",
                "agentid": int(settings.wecom_agent_id),
                "text": {"content": text},
            },
        )
        data = resp.json()

        if data.get("errcode") != 0:
            logger.error("Failed to send message: %s", data)
            return False

    return True


async def reply_message(external_userid: str, text: str) -> bool:
    """回复外部联系人消息（企业微信没有专门的reply接口，直接发送）"""
    return await send_message(external_userid, text)

"""数据模型"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class IncomingMessage:
    """飞书收到的消息"""
    user_id: str          # 飞书 open_id
    user_name: str        # 用户昵称
    chat_id: str          # 会话 ID
    chat_type: str        # "p2p" 或 "group"
    content: str          # 消息文本
    message_id: str       # 消息 ID（用于回复）
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class UserProfile:
    """用户画像"""
    user_id: str
    user_name: str
    gender: str = ""       # "male" / "female" / ""（未确认）
    call_name: str = ""    # 用户希望被怎么称呼
    first_seen: str = ""
    last_seen: str = ""
    interests: str = ""    # 关注领域
    notes: str = ""        # 备注


@dataclass
class AgentResponse:
    """Agent 回复"""
    text: str
    skill_used: str = ""   # 使用了哪个技能

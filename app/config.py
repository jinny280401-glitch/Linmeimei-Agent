"""应用配置 — 所有密钥和参数通过环境变量管理"""

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    # 飞书
    feishu_app_id: str = field(default_factory=lambda: os.getenv("FEISHU_APP_ID", ""))
    feishu_app_secret: str = field(default_factory=lambda: os.getenv("FEISHU_APP_SECRET", ""))

    # 企业微信
    wecom_corp_id: str = field(default_factory=lambda: os.getenv("WECOM_CORP_ID", ""))
    wecom_agent_id: str = field(default_factory=lambda: os.getenv("WECOM_AGENT_ID", ""))
    wecom_secret: str = field(default_factory=lambda: os.getenv("WECOM_SECRET", ""))
    wecom_token: str = field(default_factory=lambda: os.getenv("WECOM_TOKEN", ""))
    wecom_encoding_aes_key: str = field(default_factory=lambda: os.getenv("WECOM_ENCODING_AES_KEY", ""))

    # 搜索 API
    tavily_keys: list[str] = field(default_factory=lambda: [
        k.strip() for k in os.getenv("TAVILY_KEYS", "").split(",") if k.strip()
    ])
    brave_keys: list[str] = field(default_factory=lambda: [
        k.strip() for k in os.getenv("BRAVE_KEYS", "").split(",") if k.strip()
    ])

    # MiniMax
    minimax_api_key: str = field(default_factory=lambda: os.getenv("MINIMAX_API_KEY", ""))

    # 加密
    encryption_key: str = field(default_factory=lambda: os.getenv("ENCRYPTION_KEY", ""))

    # 路径
    workspace_dir: str = field(default_factory=lambda: os.getenv("WORKSPACE_DIR", "/app/workspace"))
    data_dir: str = field(default_factory=lambda: os.getenv("DATA_DIR", "/app/data"))
    users_db_dir: str = field(default_factory=lambda: os.getenv("USERS_DB_DIR", "/app/data/users"))

    # Claude Code
    claude_timeout: int = 120

    # 服务
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")


settings = Settings()

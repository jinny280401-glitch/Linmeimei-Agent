"""林妹妹 Agent v2.0 — FastAPI 入口"""

import os
import logging
from fastapi import FastAPI
from app.config import settings
from app.routers import feishu, health

# 日志配置
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 创建应用
app = FastAPI(
    title="林妹妹 Agent",
    description="基于 Claude Code 的多用户 AI Agent",
    version="2.0.0",
)

# 注册路由
app.include_router(health.router)
app.include_router(feishu.router)


@app.on_event("startup")
async def startup():
    """启动时初始化"""
    # 创建数据目录
    os.makedirs(settings.users_db_dir, exist_ok=True)

    # 检查关键配置
    if not settings.feishu_app_id:
        logger.warning("FEISHU_APP_ID not set, Feishu integration will not work")
    if not settings.feishu_app_secret:
        logger.warning("FEISHU_APP_SECRET not set, Feishu integration will not work")

    logger.info("林妹妹 Agent v2.0 started")
    logger.info("Workspace: %s", settings.workspace_dir)
    logger.info("Data dir: %s", settings.data_dir)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )

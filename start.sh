#!/bin/bash
# 林妹妹 Agent 启动脚本

cd /home/admin/.openclaw/workspace-linmeimei

# 加载环境变量
export $(cat .env | grep -v '^#' | xargs)

# 启动 OpenClaw Gateway（端口 8081，与太子团队区分）
echo "🌟 启动林妹妹 Agent Gateway..."
openclaw gateway start --port 8081

echo "✅ 林妹妹 Agent 已启动！"
echo "   - 飞书端口：8081"
echo "   - 工作区：/home/admin/.openclaw/workspace-linmeimei"

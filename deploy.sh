#!/bin/bash
# ============================================
# 林妹妹 Agent 云服务器一键部署脚本
# 支持: Ubuntu 22.04+, Debian 12+
# ============================================

set -e

echo "============================================"
echo "  林妹妹 Agent 云服务器部署"
echo "============================================"
echo ""

# 检测系统
if [ -f /etc/os-release ]; then
  . /etc/os-release
  OS=$ID
else
  echo "不支持的操作系统"; exit 1
fi

echo "[1/8] 系统: $OS $VERSION_ID"

# 安装基础依赖
echo "[2/8] 安装基础依赖..."
if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq curl git python3 python3-pip
elif [ "$OS" = "centos" ] || [ "$OS" = "rhel" ]; then
  sudo yum install -y curl git python3 python3-pip
fi

# 安装 Node.js 22
echo "[3/8] 安装 Node.js 22..."
if ! command -v node >/dev/null 2>&1 || [ "$(node -e 'console.log(process.versions.node.split(".")[0])')" -lt 22 ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi
echo "   Node.js $(node --version)"

# 安装 Claude Code
echo "[4/8] 安装 Claude Code CLI..."
if ! command -v claude >/dev/null 2>&1; then
  npm install -g @anthropic-ai/claude-code
  echo "   请运行 'claude' 完成登录认证"
fi

# 安装 cc-connect
echo "[5/8] 安装 cc-connect..."
npm install -g cc-connect@beta
echo "   cc-connect $(cc-connect --version)"

# 安装 Python 依赖
echo "[6/8] 安装 Python 依赖..."
pip3 install -q akshare requests

# 运行本地安装脚本
echo "[7/8] 安装林妹妹 Agent..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
bash "$SCRIPT_DIR/install.sh"

# 创建 systemd 服务
echo "[8/8] 创建后台守护服务..."
sudo tee /etc/systemd/system/lin-meimei.service > /dev/null << EOF
[Unit]
Description=Lin Meimei Agent (cc-connect)
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/.qclaw/workspace
ExecStart=$(which cc-connect)
Restart=always
RestartSec=10
Environment=PATH=/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin
EnvironmentFile=$HOME/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable lin-meimei

echo ""
echo "============================================"
echo "  部署完成！"
echo "============================================"
echo ""
echo "后续步骤："
echo "  1. 编辑 ~/.qclaw/workspace/USER.md 填入你的信息"
echo "  2. 创建 ~/.env 填入 API 密钥（参考 .env.example）"
echo "  3. 运行 'claude' 完成 Claude Code 登录认证"
echo "  4. 微信扫码: cc-connect weixin setup --project lin-meimei"
echo "  5. 启动服务: sudo systemctl start lin-meimei"
echo ""
echo "管理命令："
echo "  启动: sudo systemctl start lin-meimei"
echo "  停止: sudo systemctl stop lin-meimei"
echo "  状态: sudo systemctl status lin-meimei"
echo "  日志: journalctl -u lin-meimei -f"
echo ""

#!/bin/bash
# ============================================
# 林妹妹 Agent 云服务器一键部署脚本
# 支持: Ubuntu 22.04+, Debian 12+
# 用法: chmod +x deploy.sh && ./deploy.sh
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
QCLAW_WORKSPACE="$HOME/.qclaw/workspace"
CC_CONNECT_DIR="$HOME/.cc-connect"

echo ""
echo "============================================"
echo "  林妹妹 Agent · 云服务器一键部署"
echo "============================================"
echo ""

# ---- 检测系统 ----
if [ -f /etc/os-release ]; then
  . /etc/os-release
  OS=$ID
else
  echo "[错误] 不支持的操作系统，请使用 Ubuntu 22.04+ 或 Debian 12+"
  exit 1
fi
echo "[0/9] 系统: $OS $VERSION_ID"

# ---- 1. 基础依赖 ----
echo "[1/9] 安装基础依赖..."
if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq curl git python3 python3-pip
elif [ "$OS" = "centos" ] || [ "$OS" = "rhel" ] || [ "$OS" = "almalinux" ] || [ "$OS" = "rocky" ]; then
  sudo yum install -y curl git python3 python3-pip
else
  echo "   [警告] 未识别的系统 $OS，跳过基础依赖安装"
fi

# ---- 2. Node.js v24 ----
echo "[2/9] 安装 Node.js v24..."
NEED_NODE=false
if ! command -v node >/dev/null 2>&1; then
  NEED_NODE=true
else
  NODE_MAJOR=$(node -e 'console.log(process.versions.node.split(".")[0])')
  if [ "$NODE_MAJOR" -lt 22 ]; then
    NEED_NODE=true
  fi
fi

if [ "$NEED_NODE" = true ]; then
  curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi
echo "   Node.js $(node --version)"

# ---- 3. Python 依赖 ----
echo "[3/9] 安装 Python 依赖..."
pip3 install --break-system-packages -q akshare httpx requests 2>/dev/null \
  || pip3 install -q akshare httpx requests 2>/dev/null \
  || echo "   [警告] Python 依赖安装失败，请手动: pip3 install akshare httpx requests"

# ---- 4. Claude Code CLI ----
echo "[4/9] 安装 Claude Code CLI..."
if ! command -v claude >/dev/null 2>&1; then
  sudo npm install -g @anthropic-ai/claude-code
fi
echo "   Claude Code $(claude --version 2>/dev/null || echo '已安装')"

# ---- 5. cc-connect ----
echo "[5/9] 安装 cc-connect..."
sudo npm install -g cc-connect@beta
echo "   cc-connect $(cc-connect --version 2>/dev/null || echo '已安装')"

# ---- 6. 安装林妹妹 workspace + 技能包 ----
echo "[6/9] 安装林妹妹 Agent..."
bash "$SCRIPT_DIR/install.sh"

# ---- 7. 配置环境变量 ----
echo "[7/9] 配置环境变量..."
if [ ! -f "$HOME/.env" ]; then
  cp "$SCRIPT_DIR/.env.example" "$HOME/.env"
  echo "   已创建 ~/.env（请稍后编辑填入 API 密钥）"
else
  echo "   ~/.env 已存在，跳过"
fi

# ---- 8. cc-connect 配置 ----
echo "[8/9] 配置 cc-connect..."
if [ ! -f "$CC_CONNECT_DIR/config.toml" ]; then
  mkdir -p "$CC_CONNECT_DIR"
  cp "$SCRIPT_DIR/config/cc-connect.example.toml" "$CC_CONNECT_DIR/config.toml"
  echo "   已创建 ~/.cc-connect/config.toml"
else
  echo "   config.toml 已存在，跳过"
fi

# ---- 9. 创建 systemd 守护服务 ----
echo "[9/9] 创建 systemd 守护服务..."

# 找到 cc-connect 和 node 的完整路径
CC_CONNECT_PATH=$(which cc-connect)
NODE_DIR=$(dirname $(which node))

sudo tee /etc/systemd/system/lin-meimei.service > /dev/null << SERVICEEOF
[Unit]
Description=Lin Meimei Agent (cc-connect)
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$QCLAW_WORKSPACE
ExecStart=$CC_CONNECT_PATH
Restart=always
RestartSec=10
Environment=PATH=$NODE_DIR:/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin
EnvironmentFile=$HOME/.env

[Install]
WantedBy=multi-user.target
SERVICEEOF

sudo systemctl daemon-reload
sudo systemctl enable lin-meimei

echo ""
echo "============================================"
echo "  部署完成!"
echo "============================================"
echo ""
echo "---"
echo "已完成的部署清单"
echo ""
printf "  %-35s %s\n" "步骤" "状态"
printf "  %-35s %s\n" "---" "---"
printf "  %-35s %s\n" "基础依赖 (curl/git/python3)" "done"
printf "  %-35s %s\n" "Node.js $(node --version)" "done"
printf "  %-35s %s\n" "Python 3 + akshare" "done"
printf "  %-35s %s\n" "Claude Code CLI" "done"
printf "  %-35s %s\n" "cc-connect (beta)" "done"
printf "  %-35s %s\n" "林妹妹 workspace + 技能包" "done"
printf "  %-35s %s\n" "环境变量 ~/.env" "done"
printf "  %-35s %s\n" "cc-connect 配置" "done"
printf "  %-35s %s\n" "systemd 服务 lin-meimei" "done"
printf "  %-35s %s\n" "Claude OAuth 登录" "需手动"
printf "  %-35s %s\n" "微信扫码绑定" "需手动"
echo ""
echo "---"
echo ""
echo "还差 2 步（需手动操作）："
echo ""
echo "  步骤1: 编辑 API 密钥"
echo "    nano ~/.env"
echo "    # 填入 TAVILY_KEYS 和 BRAVE_KEYS"
echo ""
echo "  步骤2: Claude Code 登录"
echo "    claude"
echo "    # 按提示在浏览器完成 OAuth 授权"
echo ""
echo "  步骤3: 微信扫码绑定"
echo "    cc-connect weixin setup --project lin-meimei"
echo "    # 用手机微信扫码"
echo ""
echo "  步骤4: 启动服务"
echo "    sudo systemctl start lin-meimei"
echo ""
echo "管理命令："
echo "  启动:  sudo systemctl start lin-meimei"
echo "  停止:  sudo systemctl stop lin-meimei"
echo "  重启:  sudo systemctl restart lin-meimei"
echo "  状态:  sudo systemctl status lin-meimei"
echo "  日志:  sudo journalctl -u lin-meimei -f"
echo ""

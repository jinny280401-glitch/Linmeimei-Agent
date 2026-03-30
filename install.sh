#!/bin/bash
# ============================================
# 林妹妹 Agent 一键安装脚本（本地）
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
QCLAW_WORKSPACE="${QCLAW_WORKSPACE:-$HOME/.qclaw/workspace}"
SKILLS_DIR="$QCLAW_WORKSPACE/skills"

echo "============================================"
echo "  林妹妹 Agent 一键安装"
echo "============================================"
echo ""

# 检查依赖
echo "[0/6] 检查依赖..."
command -v node >/dev/null 2>&1 || { echo "需要 Node.js >= 22，请先安装"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "需要 Python3，请先安装"; exit 1; }
command -v claude >/dev/null 2>&1 || { echo "需要 Claude Code CLI，请先安装"; exit 1; }
echo "   Node.js $(node --version), Python3, Claude Code 已就绪"

# 创建 workspace
if [ ! -d "$QCLAW_WORKSPACE" ]; then
  mkdir -p "$QCLAW_WORKSPACE"
  echo "   创建 workspace: $QCLAW_WORKSPACE"
fi

echo "[1/6] 备份现有配置..."
BACKUP_DIR="$QCLAW_WORKSPACE/.backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
for f in SOUL.md USER.md AGENTS.md IDENTITY.md TOOLS.md CLAUDE.md; do
  [ -f "$QCLAW_WORKSPACE/$f" ] && cp "$QCLAW_WORKSPACE/$f" "$BACKUP_DIR/"
done
echo "   备份: $BACKUP_DIR"

echo "[2/6] 安装灵魂三件套..."
cp "$SCRIPT_DIR/workspace/SOUL.md" "$QCLAW_WORKSPACE/"
cp "$SCRIPT_DIR/workspace/AGENTS.md" "$QCLAW_WORKSPACE/"
cp "$SCRIPT_DIR/workspace/IDENTITY.md" "$QCLAW_WORKSPACE/"
cp "$SCRIPT_DIR/workspace/TOOLS.md" "$QCLAW_WORKSPACE/"
cp "$SCRIPT_DIR/workspace/HEARTBEAT.md" "$QCLAW_WORKSPACE/"
cp "$SCRIPT_DIR/workspace/CLAUDE.md" "$QCLAW_WORKSPACE/"
# USER.md 和 MEMORY.md 不覆盖已有的
[ ! -f "$QCLAW_WORKSPACE/USER.md" ] && cp "$SCRIPT_DIR/workspace/USER.md" "$QCLAW_WORKSPACE/"
[ ! -f "$QCLAW_WORKSPACE/MEMORY.md" ] && cp "$SCRIPT_DIR/workspace/MEMORY.md" "$QCLAW_WORKSPACE/"
echo "   灵魂三件套已安装"

echo "[3/6] 安装技能包..."
mkdir -p "$SKILLS_DIR"

# finance-suite
cp -r "$SCRIPT_DIR/skills/finance-suite" "$SKILLS_DIR/"
echo "   finance-suite（6大金融技能）已安装"

# cc-connect-bridge
cp -r "$SCRIPT_DIR/skills/cc-connect-bridge" "$SKILLS_DIR/"
echo "   cc-connect-bridge（多平台桥接）已安装"

# cc-weixin-bridge
cp -r "$SCRIPT_DIR/skills/cc-weixin-bridge" "$SKILLS_DIR/"
echo "   cc-weixin-bridge（微信桥接）已安装"

echo "[4/6] 创建客户记忆目录..."
mkdir -p "$QCLAW_WORKSPACE/memory/customers"
echo "   memory/customers/ 已创建"

echo "[5/6] 安装 Python 依赖..."
pip3 install -q akshare requests 2>/dev/null || echo "   Python 依赖安装失败，请手动: pip3 install akshare requests"

echo "[6/6] 安装 cc-connect..."
if ! command -v cc-connect >/dev/null 2>&1; then
  npm install -g cc-connect@beta 2>/dev/null && echo "   cc-connect 已安装" || echo "   cc-connect 安装失败，请手动: npm i -g cc-connect@beta"
else
  echo "   cc-connect 已存在"
fi

# 复制配置模板
if [ ! -f "$HOME/.cc-connect/config.toml" ]; then
  mkdir -p "$HOME/.cc-connect"
  cp "$SCRIPT_DIR/config/cc-connect.example.toml" "$HOME/.cc-connect/config.toml"
  echo "   cc-connect 配置已创建，请编辑 ~/.cc-connect/config.toml"
fi

echo ""
echo "============================================"
echo "  安装完成！"
echo "============================================"
echo ""
echo "后续步骤："
echo "  1. 编辑 ~/.qclaw/workspace/USER.md 填入你的信息"
echo "  2. 复制 .env.example 为 .env 并填入 API 密钥"
echo "  3. 微信扫码: cc-connect weixin setup --project lin-meimei"
echo "  4. 启动服务: cc-connect start"
echo ""

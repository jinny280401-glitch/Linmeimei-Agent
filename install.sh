#!/bin/bash
# ============================================
# 林妹妹 Agent 安装脚本
# 安装 workspace 文件和技能包到 ~/.qclaw/workspace
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
QCLAW_WORKSPACE="${QCLAW_WORKSPACE:-$HOME/.qclaw/workspace}"
SKILLS_DIR="$QCLAW_WORKSPACE/skills"

echo ""
echo "============================================"
echo "  林妹妹 Agent · 安装 workspace"
echo "============================================"
echo ""

# 创建 workspace
mkdir -p "$QCLAW_WORKSPACE"

# 备份现有配置
echo "[1/4] 备份现有配置..."
HAS_BACKUP=false
for f in SOUL.md USER.md AGENTS.md IDENTITY.md TOOLS.md CLAUDE.md HEARTBEAT.md; do
  if [ -f "$QCLAW_WORKSPACE/$f" ]; then
    HAS_BACKUP=true
    break
  fi
done

if [ "$HAS_BACKUP" = true ]; then
  BACKUP_DIR="$QCLAW_WORKSPACE/.backup-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$BACKUP_DIR"
  for f in SOUL.md USER.md AGENTS.md IDENTITY.md TOOLS.md CLAUDE.md HEARTBEAT.md MEMORY.md; do
    [ -f "$QCLAW_WORKSPACE/$f" ] && cp "$QCLAW_WORKSPACE/$f" "$BACKUP_DIR/"
  done
  echo "   已备份到: $BACKUP_DIR"
else
  echo "   首次安装，无需备份"
fi

# 安装核心文件
echo "[2/4] 安装核心文件..."
cp "$SCRIPT_DIR/workspace/SOUL.md" "$QCLAW_WORKSPACE/"
cp "$SCRIPT_DIR/workspace/AGENTS.md" "$QCLAW_WORKSPACE/"
cp "$SCRIPT_DIR/workspace/IDENTITY.md" "$QCLAW_WORKSPACE/"
cp "$SCRIPT_DIR/workspace/TOOLS.md" "$QCLAW_WORKSPACE/"
cp "$SCRIPT_DIR/workspace/HEARTBEAT.md" "$QCLAW_WORKSPACE/"
cp "$SCRIPT_DIR/workspace/CLAUDE.md" "$QCLAW_WORKSPACE/"
# USER.md 和 MEMORY.md 不覆盖已有的（保留用户自定义内容）
[ ! -f "$QCLAW_WORKSPACE/USER.md" ] && cp "$SCRIPT_DIR/workspace/USER.md" "$QCLAW_WORKSPACE/"
[ ! -f "$QCLAW_WORKSPACE/MEMORY.md" ] && cp "$SCRIPT_DIR/workspace/MEMORY.md" "$QCLAW_WORKSPACE/"
echo "   SOUL.md, CLAUDE.md, AGENTS.md 等已安装"

# 安装技能包
echo "[3/4] 安装技能包..."
mkdir -p "$SKILLS_DIR"
cp -r "$SCRIPT_DIR/skills/finance-suite" "$SKILLS_DIR/"
cp -r "$SCRIPT_DIR/skills/cc-connect-bridge" "$SKILLS_DIR/"
cp -r "$SCRIPT_DIR/skills/cc-weixin-bridge" "$SKILLS_DIR/"
echo "   finance-suite（6大金融技能）"
echo "   cc-connect-bridge（多平台桥接）"
echo "   cc-weixin-bridge（微信桥接）"

# 创建记忆目录
echo "[4/4] 创建记忆目录..."
mkdir -p "$QCLAW_WORKSPACE/memory/customers"
echo "   memory/customers/ 已就绪"

echo ""
echo "============================================"
echo "  安装完成!"
echo "============================================"
echo ""
echo "文件位置: $QCLAW_WORKSPACE"
echo ""
echo "可自定义的文件："
echo "  $QCLAW_WORKSPACE/USER.md    ← 填入你的个人信息"
echo "  $QCLAW_WORKSPACE/SOUL.md    ← 修改人设性格"
echo "  $QCLAW_WORKSPACE/CLAUDE.md  ← 修改 Claude 指令"
echo ""

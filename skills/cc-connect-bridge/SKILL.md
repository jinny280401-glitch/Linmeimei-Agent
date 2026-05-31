---
name: cc-connect-bridge
version: 1.0.0
description: >
  多平台 AI Agent 桥接技能。通过 cc-connect 将 OpenClaw/Claude Code 接入
  个人微信、企业微信、飞书、钉钉、Telegram、Slack、Discord、QQ 等10个平台。
  支持一对多架构（每个用户 chat_id 天然隔离），多Agent切换，
  Claude Code 订阅版直连，无需公网IP。
author: 林嘉勤
license: MIT
metadata:
  openclaw:
    emoji: "🌐"
    security_level: L2
    always: false
    network_behavior:
      makes_requests: true
      domains:
        - ilinkai.weixin.qq.com
        - registry.npmjs.org
      uses_agent_telegram: false
    requires:
      bins:
        - node
        - npx
---

# CC-Connect Bridge — 多平台一对多 Agent 桥接

> 一个 Agent，十个平台，每个用户独立隔离

## 支持平台

| 平台 | 协议 | 需要公网IP |
|------|------|-----------|
| 个人微信（iLink） | HTTP长轮询 | 否 |
| 企业微信 | WebSocket | 否 |
| 飞书/Lark | WebSocket | 否 |
| 钉钉 | Stream | 否 |
| Telegram | 长轮询 | 否 |
| Slack | Socket Mode | 否 |
| Discord | Gateway | 否 |
| QQ（NapCat） | WebSocket | 否 |
| QQ Bot（官方） | WebSocket | 否 |
| LINE | Webhook | 是 |

## 支持 Agent

Claude Code（订阅版）、Codex、Cursor、Gemini CLI、OpenClaw 等7种。

## 核心优势

- **一对多**：多项目架构，每个项目独立 Agent + 平台组合
- **用户隔离**：每个 chat_id 独立会话，Memory 不串
- **无需公网IP**：大部分平台走 WebSocket/长轮询
- **多Agent切换**：`/claude`、`/codex` 等命令切换
- **会话管理**：`/new`、`/list`、`/switch` 管理对话

## 安装

### 方式1：NPM（推荐）

```bash
# 稳定版（企业微信、飞书、钉钉等）
npm install -g cc-connect

# 测试版（额外支持个人微信 iLink）
npm install -g cc-connect@beta
```

### 方式2：二进制

```bash
# macOS ARM
curl -L -o cc-connect https://github.com/chenhg5/cc-connect/releases/latest/download/cc-connect-darwin-arm64
chmod +x cc-connect
sudo mv cc-connect /usr/local/bin/
```

### 方式3：源码（需 Go 1.22+）

```bash
git clone https://github.com/chenhg5/cc-connect.git
cd cc-connect && make build
```

## 配置

### 初始化配置文件

```bash
mkdir -p ~/.cc-connect
```

### 个人微信配置（config.toml）

```toml
# ~/.cc-connect/config.toml

language = "zh-CN"

[[projects]]
name = "lin-meimei"
work_dir = "/Users/你的用户名/.qclaw/workspace"

[projects.agent]
type = "claude-code"
# permission_mode = "default"  # 或 "yolo"（自动批准）

[[projects.platforms]]
type = "weixin"

[projects.platforms.options]
token = ""  # setup 后自动填入
# allow_from = "*"          # 生产环境改为具体用户ID
# account_id = "default"    # 多账号隔离用
```

### 企业微信配置

```toml
[[projects]]
name = "lin-meimei"
work_dir = "/Users/你的用户名/.qclaw/workspace"

[projects.agent]
type = "claude-code"

[[projects.platforms]]
type = "wecom"

[projects.platforms.options]
corp_id = "你的企业ID"
agent_id = "应用ID"
secret = "应用密钥"
# admin_from = "alice,bob"  # 管理员用户
```

### 飞书配置

```toml
[[projects.platforms]]
type = "feishu"

[projects.platforms.options]
app_id = "cli_xxx"
app_secret = "xxx"
```

### 钉钉配置

```toml
[[projects.platforms]]
type = "dingtalk"

[projects.platforms.options]
client_id = "xxx"
client_secret = "xxx"
```

## 启动

### 个人微信扫码

```bash
# 一键扫码绑定
cc-connect weixin setup --project lin-meimei

# 强制重新扫码（换号用）
cc-connect weixin new --project lin-meimei

# 导入已有 token
cc-connect weixin bind --project lin-meimei --token '<Bearer_Token>'
```

### 启动服务

```bash
cc-connect           # 前台运行
cc-connect start     # 后台守护进程
```

## 一对多架构说明

```
你的 OpenClaw / Claude Code
        ↓
   cc-connect（桥接层）
        ↓
   ┌────┼────┬────┐
   ↓    ↓    ↓    ↓
 用户A 用户B 用户C 用户D
 (chat_id独立，Memory隔离)
```

**关键配置**：
- `allow_from`：限制哪些用户可以使用（生产环境必填）
- `account_id`：多账号时隔离状态文件
- 每个用户的 chat_id 天然独立，不会串记忆

## 会话命令（用户在微信中发送）

```
/new [name]        新建会话
/list              列出所有会话
/switch <id>       切换会话
/current           显示当前会话
/dir [path]        切换工作目录
/memory            读写 Agent 指令文件
/claude            切换到 Claude Code
/codex             切换到 Codex
```

## 定时任务

```
/cron add 0 8 * * * 生成今日A股早报
/cron add 0 15 * * 1-5 收盘后总结今日行情
```

## 安全建议

- 生产环境 `allow_from` 必须填具体用户ID，不要留 `*`
- `permission_mode` 建议用 `default`（逐个确认），不要用 `yolo`
- 企业微信密钥建议用环境变量：`${WECOM_SECRET}`
- 定期检查会话日志，确认无异常访问

## 用户记忆隔离机制

### 目录结构

```
~/.qclaw/workspace/memory/
├── MEMORY.md                       ← 主用户（哥哥）长期记忆
├── YYYY-MM-DD.md                   ← 主用户每日笔记
└── customers/                      ← 客户独立记忆
    ├── wechat_user_001.md          ← 客户1
    ├── wechat_user_002.md          ← 客户2
    └── wecom_user_003.md           ← 企业微信客户3
```

### 消息处理逻辑

```javascript
// 收到消息时按 user_id 隔离记忆
onMessage(user_id, content) {
  // 1. 按用户加载独立记忆
  const memoryPath = `memory/customers/${user_id}.md`;
  const customerMemory = loadMemory(memoryPath);

  // 2. 结合记忆处理消息
  const response = agent.process(content, {
    context: customerMemory,
    soul: "SOUL.md",        // 共享同一个人设
    user: "USER.md"         // 共享基础配置
  });

  // 3. 回写该客户的记忆（不影响其他客户）
  saveMemory(memoryPath, {
    lastActive: new Date(),
    keyInfo: response.extractedInfo,
    history: customerMemory.history.concat(response)
  });

  return response;
}
```

### 隔离规则

- 每个客户首次对话时自动创建 `memory/customers/{user_id}.md`
- 客户之间的记忆严格隔离，绝不交叉
- 主用户（哥哥）的记忆在 `MEMORY.md`，不在 customers/ 下
- 金融投研分析按客户独立输出
- 客户记忆文件格式：

```markdown
# 客户记忆 - {user_id}

- **首次对话**：2026-03-29
- **最近活跃**：2026-03-29
- **关注领域**：（自动积累）
- **重要信息**：（自动积累）
- **偏好备注**：（自动积累）
```

### 初始化

```bash
mkdir -p ~/.qclaw/workspace/memory/customers/
```

## 与林妹妹 Agent 联动

安装本技能后，林妹妹可以通过微信/企业微信/飞书等平台服务多个用户：

1. 每个用户独立会话，妹妹记得每个人的偏好
2. 金融投研分析通过微信直接推送
3. 支持文件/图片双向传输（研报PDF、K线图等）
4. 定时任务自动推送早报/收盘总结

## 故障排查

| 问题 | 解决方案 |
|------|---------|
| 个人微信不可用 | 确认安装的是 `cc-connect@beta` |
| 扫码超时 | `--timeout 600` 延长等待时间 |
| 消息不回复 | 检查 `allow_from` 是否包含你的用户ID |
| Agent 无响应 | 检查 Claude Code 是否已登录：`claude --version` |
| 多用户串记忆 | 检查 `account_id` 配置是否正确 |

## 参考

- GitHub：https://github.com/chenhg5/cc-connect
- 个人微信文档：docs/weixin.md
- 配置模板：config.example.toml

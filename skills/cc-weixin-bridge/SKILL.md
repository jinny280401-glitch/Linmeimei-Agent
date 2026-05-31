---
name: cc-weixin-bridge
version: 1.0.0
description: >
  将 Claude Code 订阅版接入微信的桥接技能。通过腾讯官方 iLink Bot API，
  让 OpenClaw 可以通过微信驱动 Claude Code 处理任务，支持文字、图片、
  语音、文件的双向传输。适用于 Claude Code 订阅用户（非 API Key）。
author: 林嘉勤
license: MIT
metadata:
  openclaw:
    emoji: "🔗"
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
        - claude
    install:
      - id: cc-weixin-channel
        kind: node
        package: claude-code-wechat-channel
        bins: []
        label: "Install Claude Code WeChat Channel (npm)"
---

# CC-WeChat Bridge — 微信驱动 Claude Code

> 让你的 OpenClaw 通过微信指挥 Claude Code 干活

## 功能

- 微信消息 ↔ Claude Code 双向桥接
- 支持 Claude Code **订阅版**（OAuth 认证，无需 API Key）
- 基于腾讯官方 iLink Bot API（合规安全）
- Claude Code 完整工具能力：Bash执行、文件读写、网页搜索
- 轻量级，核心代码约200行

## 前置要求

| 依赖 | 最低版本 | 检查命令 |
|------|---------|---------|
| Node.js | >= 22 | `node --version` |
| Claude Code | >= 2.1.80 | `claude --version` |
| 微信 iOS | 最新版 | 需支持 ClawBot |

## 安装与配置

### 第一步：生成 MCP 配置

```bash
npx claude-code-wechat-channel install
```

这会在 `~/.mcp.json` 生成配置：

```json
{
  "mcpServers": {
    "wechat": {
      "command": "npx",
      "args": ["-y", "claude-code-wechat-channel", "start"]
    }
  }
}
```

### 第二步：微信扫码授权

```bash
npx claude-code-wechat-channel setup
```

- 终端会显示二维码，用微信扫码
- 扫码后在手机上确认授权
- 登录凭证自动保存到 `.weixin-token.json`（下次免扫码）

### 第三步：启动通道

```bash
claude --dangerously-load-development-channels server:wechat
```

启动后，在微信中给 ClawBot 发消息即可驱动 Claude Code。

## 快速一键启动（已完成 setup 后）

```bash
claude --dangerously-load-development-channels server:wechat
```

## 重新登录（Token 过期时）

```bash
npx claude-code-wechat-channel setup --login
```

## TUI 快捷键

| 按键 | 功能 |
|------|------|
| L | 登出并退出 |
| R | 重连 |
| Q | 退出 |

## 架构说明

```
微信用户 ──(iLink API)──▶ cc-weixin-bridge ──(Agent SDK)──▶ Claude Code
   ◀──(iLink API)──  结果返回  ◀──(stdout)──  执行结果
```

通信链路：
1. **微信 ↔ Bridge**：通过 iLink Bot API（HTTP 长轮询），域名 `ilinkai.weixin.qq.com`
2. **Bridge ↔ Claude Code**：通过 Claude Agent SDK，使用本地 OAuth 认证

## OpenClaw 联动

在 OpenClaw 中，可以通过微信渠道向 Claude Code 发送指令：

1. OpenClaw 收到用户微信消息
2. 判断需要 Claude Code 处理的任务（如代码编写、文件操作）
3. 通过微信转发给 Claude Code 通道
4. Claude Code 执行后结果回传微信

### 适用场景

- 在微信里让 Claude Code 写代码、改文件
- 远程触发 Claude Code 执行自动化脚本
- OpenClaw 分发任务给 Claude Code 处理复杂开发需求
- 手机端随时随地驱动本地 Claude Code

## 安全说明

- 仅使用腾讯官方 iLink API，不走第三方服务器
- 登录凭证本地存储（`.weixin-token.json`），不上传
- Claude Code 使用本地 OAuth 认证，无需暴露 API Key
- 建议仅在私聊中使用，避免群聊中误触发

## 故障排查

| 问题 | 解决方案 |
|------|---------|
| 二维码过期 | 重新运行 `npx claude-code-wechat-channel setup` |
| Token 失效 | 运行 `npx claude-code-wechat-channel setup --login` |
| Claude Code 版本过低 | 运行 `claude update` 升级到 >= 2.1.80 |
| 连接断开 | 按 `R` 键重连，或重启通道 |
| 微信无 ClawBot | 确认微信 iOS 为最新版本，检查是否开通 ClawBot |

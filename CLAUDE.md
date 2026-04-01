# 林妹妹 Agent v2.0 — 项目规范

## 项目概述

基于 FastAPI + Claude Code 的多用户 AI Agent 系统。
通过飞书企业应用接入，支持多用户并发，每用户独立记忆隔离。

## 技术栈

- 后端：FastAPI (Python 3.11+)
- AI 引擎：Claude Code CLI（OAuth 订阅版）
- 渠道：飞书企业应用（WebSocket 长连接，无需公网 IP）
- 记忆存储：SQLite（每用户独立数据库）
- 部署：Docker + docker-compose
- 云服务器：阿里云 / 腾讯云（2核4G）

## 目录结构

```
Linmeimei-Agent/
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # 配置管理（环境变量）
│   ├── routers/
│   │   ├── feishu.py           # 飞书事件回调
│   │   └── health.py           # 健康检查
│   ├── services/
│   │   ├── agent.py            # Claude Code 交互层
│   │   ├── memory.py           # 用户记忆管理（SQLite）
│   │   └── feishu_client.py    # 飞书 API 客户端
│   ├── skills/
│   │   ├── router.py           # 意图路由
│   │   ├── finance.py          # 金融投研
│   │   ├── sales.py            # 销售军师
│   │   ├── client_sandbox.py   # 客户沙盘推演
│   │   └── company_matcher.py  # 上市公司业务匹配
│   └── models/
│       └── schemas.py          # 数据模型
├── workspace/                  # 人设文件（SOUL.md 等）
├── skills/                     # Skill 定义（SKILL.md）
├── data/
│   └── users/                  # 用户 SQLite 数据库
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env
```

## 架构

```
用户（飞书）
    ↓ 消息
飞书开放平台
    ↓ WebSocket 事件推送
FastAPI（app/routers/feishu.py）
    ↓ 解析 user_id + 消息内容
意图路由（app/skills/router.py）
    ↓ 匹配技能模块
Claude Code CLI（subprocess）
    ↓ 执行分析/生成回复
记忆系统（app/services/memory.py）
    ↓ 读写用户独立 SQLite
FastAPI → 飞书 API 回复用户
```

## 代码规范

- Python 代码遵循 PEP 8
- 类型注解：所有函数参数和返回值必须标注类型
- 异步优先：FastAPI 路由和 I/O 操作用 async/await
- 环境变量：所有密钥通过 .env 管理，不硬编码
- 日志：使用 Python logging，不用 print
- 错误处理：外部 API 调用必须有 try/except 和重试

## 飞书集成规范

- 事件订阅使用 WebSocket 长连接模式（不需要公网回调 URL）
- 群聊中仅响应 @机器人 的消息
- 私聊中响应所有消息
- 回复使用纯文本，不用 Markdown（飞书虽然支持但保持一致性）
- 每条消息处理超时上限 120 秒

## 记忆系统规范

- 每个用户一个独立 SQLite 文件：data/users/{user_id}.db
- 表结构：
  - user_profile（性别、称呼偏好、首次交互时间）
  - conversations（消息历史，保留最近 100 轮）
  - key_facts（用户关键信息，如关注领域、偏好等）
  - client_files（投顾的客户档案，沙盘推演用）
- 用户数据严格隔离，A 的数据不能出现在 B 的上下文中

## 人设规范

- 人设定义在 workspace/SOUL.md 和 workspace/CLAUDE.md
- 所有用户共享同一个人设（林妹妹/嘉勤）
- 用户个性化信息存在各自的 SQLite 中
- 新用户首次交互必须询问性别，确认前用"你"称呼

## 安全规范

- 飞书 app_secret 不入仓库
- 用户数据目录 data/users/ 不入仓库
- Claude Code 使用 OAuth 认证，不暴露 API Key
- 金融分析末尾标注"仅供参考，不构成投资建议"
- 客户档案数据严格隔离，不同投顾之间不交叉

# 林妹妹 Agent — 技术架构 v2.0

## 架构总览

```
                    用户侧（飞书）
        ┌──────────┬──────────┬──────────┐
        │  用户 A  │  用户 B  │  用户 C  │
        └────┬─────┴────┬─────┴────┬─────┘
             │          │          │
             ▼          ▼          ▼
    ┌─────────────────────────────────────┐
    │     飞书开放平台（企业应用）          │
    │     WebSocket 长连接，无需公网 IP     │
    └─────────────────┬───────────────────┘
                      │ 事件推送
                      ▼
    ┌─────────────────────────────────────┐
    │     FastAPI 服务层                   │
    │                                     │
    │  ┌─────────┐  ┌──────────────────┐  │
    │  │ 飞书路由 │  │   意图路由引擎    │  │
    │  │ 收发消息 │→ │ 关键词匹配技能   │  │
    │  └─────────┘  └────────┬─────────┘  │
    │                        │            │
    │  ┌─────────────────────┼──────────┐ │
    │  │     技能模块层       │          │ │
    │  │                     ▼          │ │
    │  │  ┌────────┐ ┌────────────────┐ │ │
    │  │  │金融投研 │ │   销售军师     │ │ │
    │  │  │6 技能   │ │   话术生成     │ │ │
    │  │  └────────┘ └────────────────┘ │ │
    │  │  ┌────────┐ ┌────────────────┐ │ │
    │  │  │客户沙盘 │ │ 上市公司匹配   │ │ │
    │  │  │优先排序 │ │  拜访准备      │ │ │
    │  │  └────────┘ └────────────────┘ │ │
    │  └────────────────────────────────┘ │
    │                                     │
    │  ┌──────────┐  ┌──────────────────┐ │
    │  │记忆系统   │  │  Claude Code    │ │
    │  │用户独立   │  │  CLI 调用       │ │
    │  │SQLite    │  │  OAuth 认证     │ │
    │  └──────────┘  └──────────────────┘ │
    └─────────────────────────────────────┘
                      │
              Docker 容器化部署
                      │
    ┌─────────────────────────────────────┐
    │     云服务器（阿里云 / 腾讯云）       │
    │     2核4G，Ubuntu 22.04             │
    └─────────────────────────────────────┘
```

## 为什么从 v1 升级到 v2

v1.0（cc-connect + 微信 ClawBot）的致命问题：

| 问题 | 影响 |
|------|------|
| 单一用户限制 | 扫码登录会踢掉前一个管理员 |
| 需要专用微信号 | 必须释放一个号当"中台" |
| 链路太长 | 用户→管理员微信→Agent→回传 |
| 无法并发 | 多用户消息会冲突 |

v2.0 的改进：

| 维度 | v1.0 | v2.0 |
|------|------|------|
| 渠道 | 微信个人号 | 飞书企业应用 |
| 多用户 | 单用户 | 原生多用户 |
| 记忆 | Markdown 文件 | SQLite（每用户独立） |
| 桥接 | cc-connect | FastAPI（完全可控） |
| 部署 | systemd | Docker |
| 成本 | 需专用微信号 | 免费创建飞书应用 |

## 核心模块

### 1. 飞书事件处理（app/routers/feishu.py）

- 接收飞书 WebSocket 推送的消息事件
- 解析 user_id（open_id）、chat_type、消息内容
- 群聊去除 @机器人 文本
- 消息去重（防止飞书超时重发）
- 异步处理（立即返回 200，后台处理并回复）

### 2. 意图路由（app/skills/router.py）

- 关键词匹配，命中则加载对应 SKILL.md 作为上下文
- 未命中任何技能则走日常闲聊
- 路由表可扩展，新增技能只需加一条路由规则

### 3. 记忆系统（app/services/memory.py）

- 每用户独立 SQLite 文件：data/users/{user_id}.db
- 4 张表：user_profile / conversations / key_facts / client_files
- 对话历史自动裁剪，保留最近 100 轮
- 用户上下文自动注入给 Claude（性别、称呼、关注领域、近期对话）

### 4. Claude Code 调用（app/services/agent.py）

- 通过 subprocess 调用 claude CLI
- 注入：人设（SOUL.md）+ 指令（CLAUDE.md）+ 用户上下文 + 技能 Prompt
- 超时处理（120 秒上限）
- 错误降级（返回友好提示，不暴露技术细节）

### 5. 飞书 API 客户端（app/services/feishu_client.py）

- tenant_access_token 自动管理（缓存 + 过期刷新）
- 消息回复（reply_message）
- 主动发送（send_message，用于定时推送）
- 用户信息查询（get_user_info）

## 技能清单

### 已完成（v1 已验证）

| 技能 | 模块 | 状态 |
|------|------|------|
| 看票分析（个股 9 章深度） | finance-suite | 已完成 |
| 宏观内参 | finance-suite | 已完成 |
| 麦肯锡报告 | finance-suite | 已完成 |
| 视频拆解 | finance-suite | 已完成 |
| 行业报告 | finance-suite | 已完成 |
| 集合竞价 | finance-suite | 已完成 |
| 微信 24 小时助理 | cc-connect | 已完成（v1 验证） |

### v2 新增（框架已搭建）

| 技能 | 模块 | 状态 |
|------|------|------|
| 销售军师 | sales-advisor | SKILL.md 已定义 |
| 客户沙盘推演 | client-sandbox | SKILL.md 已定义 |
| 上市公司业务匹配 | company-matcher | SKILL.md 已定义 |

### 规划中

| 技能 | 优先级 |
|------|--------|
| 早报/每日摘要推送 | 高 |
| 记账追踪 | 高 |
| 定时提醒 | 中 |
| 链接/文章摘要 | 中 |

## 部署

### 开发环境

```bash
pip install -r requirements.txt
cp .env.example .env   # 填入密钥
python -m app.main
```

### 生产环境（Docker）

```bash
cp .env.example .env   # 填入密钥
docker compose up -d

# 首次需要进容器完成 Claude OAuth 登录
docker exec -it lin-meimei-agent claude
```

### 飞书应用配置

1. https://open.feishu.cn → 创建企业应用
2. 获取 App ID + App Secret → 填入 .env
3. 添加权限：接收消息、发送消息、获取用户信息
4. 事件订阅 → 选择 WebSocket 长连接 → 添加 im.message.receive_v1
5. 发布应用

## 数据流

```
用户发消息 "帮我看一下比亚迪"
    │
    ▼
飞书推送事件 → feishu.py 解析
    │
    ▼
提取 user_id = "ou_xxxx"
    │
    ├── memory.py: 读取 data/users/ou_xxxx.db
    │   → 用户画像 + 最近对话
    │
    ├── router.py: "看票" 命中 → stock-analyst
    │   → 加载 prompts/stock-analyst.md
    │
    ▼
agent.py: 调用 Claude Code CLI
    │  注入：SOUL.md + CLAUDE.md + 用户上下文 + 技能 Prompt
    │
    ▼
Claude 执行分析（调用 stock_data.py + search.py）
    │
    ▼
返回分析报告 → memory.py 保存对话
    │
    ▼
feishu_client.py → 飞书 API 回复用户
```

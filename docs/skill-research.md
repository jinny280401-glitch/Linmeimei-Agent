# 林妹妹 Agent · Skill 扩展调研报告

调研日期：2026-04-01

## 一、同类项目（直接可参考）

| 项目 | Stars | 说明 | 地址 |
|------|-------|------|------|
| chatgpt-on-wechat (CowAgent) | 42.7k | 最成熟的微信 AI 助手，有插件系统 + Skills 引擎 | https://github.com/zhayujie/chatgpt-on-wechat |
| OpenClaw | 343k | 个人 AI Agent 标准框架，ClawHub 有 13,700+ 社区 skill | https://github.com/openclaw/openclaw |
| OpeniLink Hub | 578 | 微信 Bot 管理平台 + App 商城（天气、记账、RSS、地图等 20+ 应用） | https://github.com/openilink/openilink-hub |
| WeClaw | 1k | 专门做微信 ClawBot/iLink 协议的 Agent 桥接 | https://github.com/fastclaw-ai/weclaw |
| Nanobot | 37.4k | 超轻量 OpenClaw 替代品，内置 WeChat/Slack 等渠道 | https://github.com/HKUDS/nanobot |
| AstrBot | 28.5k | 多平台 IM 聊天 Bot 框架，支持 MCP + 插件 | https://github.com/AstrBotDevs/AstrBot |
| Mycel (菌丝) | - | 开源多 Agent 协作平台，支持微信 API | https://www.80aj.com/2026/03/22/mycel-ai-agent-team/ |
| Nexu | - | OpenClaw 桌面客户端，一键桥接 WeChat/Feishu/Slack/Discord | https://github.com/nexu-io/nexu |
| claude-code-wechat-channel | - | Claude Code WeChat Channel 插件，架构与 cc-connect 类似 | https://github.com/Johnixr/claude-code-wechat-channel |
| Wechaty | - | 微信 RPA SDK，6 行代码创建 bot，生态成熟 | https://github.com/wechaty/wechaty |

## 二、Skill 资源库

| 资源 | Stars | 内容 | 地址 |
|------|-------|------|------|
| awesome-openclaw-skills | 43.5k | 5,200+ OpenClaw skill，分类齐全 | https://github.com/VoltAgent/awesome-openclaw-skills |
| awesome-agent-skills | 13.6k | 1,060+ Claude Code 兼容 skill（Anthropic/Vercel/Stripe 官方出品） | https://github.com/VoltAgent/awesome-agent-skills |
| claude-skills | 8.4k | 220+ Claude Code skill（工程/营销/产品/合规） | https://github.com/alirezarezvani/claude-skills |
| claude-code-plugins-plus-skills | - | 340 插件 + 1,367 skill 合集 | https://github.com/jeremylongshore/claude-code-plugins-plus-skills |
| Humanizer-zh | 5.4k | 中文去 AI 痕迹 skill，让回复更像真人 | https://github.com/op7418/Humanizer-zh |
| awesome-mcp-servers | 5.3k | MCP 服务器列表（Gmail、日历、天气、RSS 等） | https://github.com/appcypher/awesome-mcp-servers |
| awesome-claude-code | - | Claude Code skill/hook/插件精选列表 | https://github.com/hesreallyhim/awesome-claude-code |
| Claude-Plugins.dev | - | Skill 发现和安装市场 | https://claude-plugins.dev/skills |
| planning-with-files | 17.8k | 持久化 Markdown 规划 skill，与我们的记忆系统互补 | https://github.com/OthmanAdi/planning-with-files |

## 三、推荐接入的 Skill

### 高优先级（日常高频使用）

| Skill | 功能 | 参考来源 |
|-------|------|---------|
| 早报/每日摘要 | 每天早上推送天气+日历+新闻+A股盘前数据 | OpeniLink Hub、awesome-openclaw-usecases |
| 记账追踪 | "午饭35"、"打车28"，自然语言记账，月度汇总 | OpeniLink Hub 记账 App、aholake-expense-tracker |
| 定时提醒 | "提醒我3点开会"，自然语言设置提醒 | CowAgent 内置、cc-connect cron |
| 链接/文章摘要 | 发一个 URL，林妹妹帮你提炼要点 | Firecrawl skill |
| RSS 订阅监控 | 监控关注的信息源，有更新主动推送 | OpeniLink Hub RSS App |

### 中优先级（提升体验）

| Skill | 功能 | 参考来源 |
|-------|------|---------|
| 中文去 AI 味 | 让回复更自然、更像真人说话 | Humanizer-zh |
| 习惯打卡 | "喝水8杯"、"运动30分钟"，每周汇总 | beaverhabits skill |
| 图片生成 | 文字生成图片 | Replicate skill、Composio |
| 文档解析 | PDF/Word/Excel 文件解析和总结 | Anthropic 官方 skill |
| 翻译 | Claude 本身就会，加一个格式化输出的 skill | 内置能力增强 |
| 音乐推荐/生成 | 接入 Suno 生成 AI 音乐 | suno-music skill |

### 低优先级（锦上添花）

| Skill | 功能 |
|-------|------|
| 智能家居控制 | IoT 设备控制 |
| 番茄钟 | 专注/工作时间管理 |
| 菜谱推荐 | 根据饮食偏好推荐食谱 |
| 健康/健身追踪 | 食物拍照算热量、运动建议 |
| 阅读清单管理 | 保存文章、追踪阅读进度 |
| 旅行规划 | 行程规划、酒店推荐 |

## 四、架构对比

| 项目 | Agent 引擎 | 桥接/渠道 | Skill 体系 |
|------|-----------|----------|-----------|
| 林妹妹 Agent（我们） | Claude Code | cc-connect (WeChat iLink) | Claude Code Skills (SKILL.md) |
| CowAgent | 多 LLM（OpenAI/Claude 等） | 原生渠道 | 插件系统 + Skills 引擎 |
| Nanobot | OpenRouter / 多 LLM | 内置渠道（WeChat/Slack 等） | 模块化 skills 目录 |
| OpenClaw | Claude / 多 LLM | Connectors（Telegram/WhatsApp 等） | ClawHub 注册表（13,700+ skills） |
| Nexu | 任意 LLM（BYOK） | 桌面 App 桥接 | 继承 OpenClaw skills |

## 五、下一步建议

1. 优先做"早报推送" -- 让林妹妹从"被动回复"变成"主动关心"，结合 cc-connect cron 定时触发
2. 接入"记账追踪" -- 与现有金融投研能力天然互补，数据存在 memory/customers/ 下按用户隔离
3. 研究 Humanizer-zh -- 提升中文回复的自然度，减少 AI 味
4. 浏览 awesome-agent-skills 和 awesome-openclaw-skills -- 挑选可直接移植的 skill
5. 关注 OpeniLink Hub 的 App 商城 -- 其 WeChat + App 的模式与我们的架构最接近

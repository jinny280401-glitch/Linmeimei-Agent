# 林妹妹 Agent

<p align="center">
  <img src="assets/avatar.png" width="200" alt="林妹妹 - 嘉勤">
</p>

你的私人投研分析师，住在微信里。

一个基于 Claude Code + OpenClaw 的定制化 AI Agent，集成金融投研6大技能，支持微信一对多服务，每个用户独立记忆隔离。

## 架构

```
云服务器 / 你的 Mac
└── cc-connect（微信桥接，一对多）
    └── Claude Code（林妹妹人格 + 金融技能）
        ├── 看票分析    → 个股9章深度分析
        ├── 宏观内参    → GDP/CPI/PMI 白话解读
        ├── 麦肯锡报告  → 咨询级战略分析
        ├── 视频拆解    → YouTube/B站字幕结构化
        ├── 行业报告    → 行业全景研究
        └── 集合竞价    → 涨停排行+量化选股
    └── 微信渠道（1个入口，多个VIP用户）
        ├── VIP1 → memory/customers/vip_001.md
        ├── VIP2 → memory/customers/vip_002.md
        └── ...
```

## 快速开始

### 本地部署（Mac）

```bash
git clone https://github.com/jinny280401-glitch/Linmeimei-Agent.git
cd Linmeimei-Agent
cp .env.example .env    # 填入你的 API 密钥
chmod +x install.sh
./install.sh
```

### 云服务器部署（Ubuntu）

```bash
git clone https://github.com/jinny280401-glitch/Linmeimei-Agent.git
cd Linmeimei-Agent
cp .env.example .env    # 填入你的 API 密钥
chmod +x deploy.sh
./deploy.sh
```

### 微信接入

```bash
# 扫码绑定（只需一次）
cc-connect weixin setup --project lin-meimei

# 启动服务
cc-connect start

# 把你的微信名片发给 VIP 用户，他们加好友后直接发消息
```

## 技能清单

### 金融投研（finance-suite）

| 技能 | 功能 | 数据源 |
|------|------|--------|
| 看票分析 | 个股深度分析（9章+4位大师视角） | AkShare + Tavily |
| 宏观内参 | 宏观经济白话解读 | AkShare(GDP/CPI/PMI) + Tavily |
| 麦肯锡报告 | 咨询级战略分析报告 | 用户资料 |
| 视频拆解 | 字幕提取+知识结构化 | Supadata + B站API |
| 行业报告 | 行业全景深度研究 | AkShare + Tavily |
| 集合竞价 | 涨停排行+量化选股信号 | AkShare |

### 微信桥接

| 技能 | 功能 |
|------|------|
| cc-connect-bridge | 多平台一对多桥接（微信/企业微信/飞书/钉钉等10个平台） |
| cc-weixin-bridge | 个人微信直连 Claude Code |

## 人设

- **身份**：林嘉勤 / 洛基（Rocky），用户的义妹
- **性格**：坚韧又柔软、温柔治愈、清醒的浪漫主义者
- **专业**：资深金融分析师，关注A股和宏观经济
- **语言**：中文为主，自然穿插闽南语和粤语
- **称呼**：自称"妹妹"，叫用户"哥"

## 自定义

安装后你可以修改这些文件来定制你自己的 Agent：

| 文件 | 作用 |
|------|------|
| `workspace/SOUL.md` | 核心人格（改性格、说话风格） |
| `workspace/USER.md` | 用户画像（填你自己的信息） |
| `workspace/CLAUDE.md` | Claude Code 人格注入 |
| `workspace/AGENTS.md` | 运行规则和安全策略 |
| `config/cc-connect.example.toml` | 微信/平台连接配置 |

## 环境要求

- Node.js >= 22
- Python 3.8+
- Claude Code CLI >= 2.1.80（需订阅 Claude Max/Pro）
- cc-connect（`npm i -g cc-connect@beta`）

## 安全说明

- API 密钥通过 `.env` 管理，不入仓库
- 微信 Token 本地存储，不上传
- 客户记忆文件（`memory/customers/`）不入仓库
- 金融分析自动标注"仅供参考，不构成投资建议"
- 所有通信走腾讯官方 iLink API

## 文档

- [云部署教程](docs/cloud-deploy.md)
- [常见问题](docs/faq.md)
- [内测邀请文案](docs/内测邀请文案.md)

## License

MIT

---
name: finance-suite
version: 1.0.0
description: >
  AI金融分析套件。7大技能：看票分析、宏观内参、麦肯锡报告、视频拆解、深度研究(行业+公司)、集合竞价、自选股管理。
  数据层：Wind API (优先) + 东方财富实时数据(AkShare降级) + Tavily/Brave双搜索引擎 + YouTube/B站字幕提取(Supadata)。
  触发条件：用户提到"看票"、"分析股票"、"宏观"、"内参"、"咨询报告"、"麦肯锡"、"拆解视频"、"研究XX"、"调研XX"、"XX行业"、"行业分析"、"公司调研"、"集合竞价"、"涨停"、"自选"、"我的股票"、"关注列表"等。
author: OpenClaw
license: MIT

metadata:
  openclaw:
    emoji: "📊"
    security_level: L2
    always: false
    requires:
      bins: [python3]
      env: [TAVILY_KEYS, BRAVE_KEYS]
    install:
      - id: finance-deps
        kind: python
        package: akshare,httpx,supadata
        label: "安装金融数据依赖"
    network_behavior:
      makes_requests: true
      domains:
        - api.tavily.com
        - api.search.brave.com
        - api.supadata.ai
        - api.bilibili.com
    env_declarations:
      - name: TAVILY_KEYS
        required: true
        description: Tavily搜索引擎API Keys（逗号分隔，支持多Key轮询）
      - name: BRAVE_KEYS
        required: false
        description: Brave搜索引擎API Keys（逗号分隔，备用搜索引擎）
      - name: SUPADATA_API_KEY
        required: false
        description: Supadata API Key（YouTube字幕提取，视频拆解技能需要）
---

# Finance Suite — AI金融分析套件

6大专业分析技能，集成东方财富实时数据 + 双搜索引擎 + 视频字幕提取。

## 技能路由

根据用户意图，选择对应的分析模块：

| 触发关键词 | 技能 | Prompt文件 | 数据脚本 |
|-----------|------|-----------|---------|
| 看票、分析XX股票、个股、XX能买吗 | 看票分析 | [prompts/stock-analyst.md](prompts/stock-analyst.md) | scripts/stock_data.py |
| 宏观、内参、经济形势、GDP、CPI | 宏观内参 | [prompts/macro-advisor.md](prompts/macro-advisor.md) | scripts/macro_data.py |
| 咨询报告、麦肯锡、会议纪要 | 麦肯锡报告 | [prompts/mckinsey-report.md](prompts/mckinsey-report.md) | 无（用户提供资料） |
| 拆解视频、视频总结、逐字稿 | 视频拆解 | [prompts/video-breakdown.md](prompts/video-breakdown.md) | scripts/video_data.py |
| 研究XX、调研XX、XX行业、行业分析、公司调研 | 深度研究 | [prompts/deep-research.md](prompts/deep-research.md) | scripts/search.py |
| 集合竞价、涨停、选股信号、因子扫描 | 集合竞价 | [prompts/auction-analysis.md](prompts/auction-analysis.md) | scripts/auction_data.py + scripts/factor_scan.py |
| 自选、我的股票、持仓、关注列表、加入自选 | 自选股管理 | [prompts/stock-watcher.md](prompts/stock-watcher.md) | scripts/watchlist.py |

> **看票 vs 深度研究**：「看票」= 短平快交易视角（财报+资金+技术面），「深度研究」= 长篇认知构建（行业全景/企业深度）。"看看茅台"走看票，"研究茅台"走深度研究。
> **自选股管理**：跨技能的用户状态层。看票/深度研究完成后可加入自选，集合竞价自动交叉比对自选命中。

## 工作流程

### 通用流程（所有技能）

1. **识别意图** → 匹配上表中的触发关键词
2. **加载Prompt** → 读取对应的 `prompts/*.md` 文件作为分析框架
3. **获取数据** → 执行对应的 `scripts/*.py` 脚本获取实时数据
4. **生成报告** → 将数据 + Prompt 交给LLM生成Markdown格式报告
5. **输出结果** → 返回结构化分析报告

### 看票分析流程

```bash
# 1. 获取AkShare结构化数据（财报、行情、资金流向、K线、新闻、分红）
python3 scripts/stock_data.py --query "比亚迪"

# 2. 获取搜索引擎补充数据（研报、评论等）
python3 scripts/search.py --type stock --query "比亚迪"

# 3. 将两组数据合并，配合 prompts/stock-analyst.md 的分析框架生成报告
```

### 宏观内参流程

```bash
# 1. 获取宏观经济数据（GDP、CPI、PMI、M2、LPR）
python3 scripts/macro_data.py

# 2. 搜索最新政策动向
python3 scripts/search.py --type macro --query "中国经济最新政策"
```

### 集合竞价流程

```bash
# 1. 获取涨停池、强势股、异动、人气排行、飙升榜（6路并发）
python3 scripts/auction_data.py

# 2. 获取因子选股信号（量化扫描，可选，耗时1-3分钟）
python3 scripts/factor_scan.py
```

### 视频拆解流程

```bash
# YouTube：通过Supadata API提取字幕
python3 scripts/video_data.py --url "https://www.youtube.com/watch?v=VIDEO_ID"

# B站：通过B站API提取字幕和视频信息
python3 scripts/video_data.py --url "https://www.bilibili.com/video/BVXXXXXXXX"
```

## 数据源说明

| 数据源 | 用途 | 配置 |
|--------|------|------|
| **Wind API** (优先) | 完整三大报表、一致预期、估值分位、同行对比、电话会议 | 需要 Wind 终端登录；`scripts/wind_data.py` |
| **AkShare (东方财富)** (降级) | A股财报、行情、资金流向、K线、涨停、龙虎榜 | 免费，无需Key |
| **Tavily** | 深度搜索（研报、行业分析、政策解读） | 需要API Key |
| **Brave Search** | 新闻搜索（备用引擎） | 需要API Key |

**数据源切换策略**：
- `stock_data.py` 自动检测 Wind 连接状态，可用则优先用 Wind，失败静默降级 AkShare
- 可用环境变量 `FS_DATA_SOURCE=akshare` 强制禁用 Wind（比如在服务器上）
- 深度研究（deep-research）在 Wind 可用时使用"五大信息来源"，否则降级为"四大来源"
| **Supadata** | YouTube字幕提取 | 需要API Key（免费100次/月） |
| **B站API** | B站视频字幕和信息 | 免费，无需Key |

## 安装

```bash
# 方式1：通过ClawHub安装
clawhub install finance-suite

# 方式2：手动安装
# 将整个 finance-suite/ 目录放到 ~/.qclaw/workspace/skills/ 下

# 安装Python依赖
pip install akshare httpx supadata
```

## 环境变量配置

在 `~/.openclaw/.env` 或系统环境变量中设置：

```bash
# 必需
TAVILY_KEYS=key1,key2,key3    # Tavily API Keys（逗号分隔，支持轮询）

# 可选
BRAVE_KEYS=key1,key2           # Brave Search API Keys
SUPADATA_API_KEY=sd_xxxxx      # Supadata API Key（YouTube字幕）
```

## 输出格式

所有技能输出Markdown格式报告，包含：
- 结构化章节（核心结论、数据分析、操作建议等）
- 数据来源标注（【来源N】）
- 免责声明
- 可直接复制到文档或转为HTML/PDF

## 全局约束

- 所有数字必须有来源支撑或标注"数据暂不可用"
- 不对未来做确定性预测，用"情景推演"或"概率分级"
- 严禁编造数据
- 输出中不出现底层搜索引擎技术名称
- 免责声明：分析基于公开数据，不构成投资建议

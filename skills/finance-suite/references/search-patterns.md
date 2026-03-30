# 搜索查询模板库

各子技能在调用 `search.sh` 时的推荐查询模板。根据实际需求调整关键词。

---

## 股票分析（stock-analyst）

```bash
# 财报数据
search.sh --type stock --query "{股票名} 最新财报 营收 净利润 毛利率 {年份}"

# 资金流向
search.sh --type stock --query "{股票名} 主力资金 北向资金 大单成交 近5日"

# 个股新闻
search.sh --type news --query "{股票名} 股票 最新消息 公告 增持 减持"

# 行业对比
search.sh --type stock --query "{股票名} 同行业对比 估值 PE PB"

# 机构研报
search.sh --type stock --query "{股票名} 研报 评级 目标价 2026"
```

## 宏观经济（macro-advisor）

```bash
# GDP与经济总量
search.sh --type macro --query "中国 GDP 经济增长 最新数据 {年份}"

# 货币政策
search.sh --type macro --query "央行 LPR 利率 货币政策 最新"

# 财政政策
search.sh --type macro --query "财政部 专项债 减税 财政政策 {年份}"

# 房地产
search.sh --type macro --query "房地产 销售 房价 政策 最新"

# 就业与消费
search.sh --type macro --query "CPI PPI 消费数据 就业 最新"

# 外部环境
search.sh --type news --query "美联储 汇率 中美贸易 地缘政治"
```

## 行业研究（industry-report）

```bash
# 市场规模
search.sh --type industry --query "{行业} 市场规模 增长率 CAGR {年份}"

# 竞争格局
search.sh --type industry --query "{行业} 头部企业 市场份额 龙头"

# 技术路线
search.sh --type industry --query "{行业} 核心技术 专利数量 研发投入"

# 政策环境
search.sh --type news --query "{行业} 行业政策 监管 标准 {年份}"

# 投融资
search.sh --type industry --query "{行业} 融资 并购 IPO 投资 最新"

# ESG
search.sh --type industry --query "{行业} ESG 碳中和 环保合规"
```

## 视频拆解（video-breakdown）

```bash
# 视频页面内容提取
search.sh --type extract --url "{视频URL}"

# 补充背景搜索（当视频内容涉及专业领域时）
search.sh --type news --query "{视频主题关键词} 最新进展"
```

## 通用技巧

1. **时间范围**：财报用 `--range month`，新闻用 `--range week`，突发事件用 `--range day`
2. **结果数量**：概览用 `--max 3`，深度分析用 `--max 8`
3. **中英文混搜**：A股用中文查询，港美股可加英文关键词
4. **多轮搜索**：第一轮粗搜确定方向，第二轮精搜补充细节

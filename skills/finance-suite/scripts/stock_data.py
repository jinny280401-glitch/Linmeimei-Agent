"""
AkShare 数据获取模块
通过东方财富/同花顺/乐咕等数据源获取A股结构化数据
所有函数经过实测验证，参数与AkShare 1.18.48一致

独立CLI脚本，无内部依赖
用法: python3 stock_data.py --query "比亚迪"
"""

import asyncio
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

import akshare as ak

# 线程池（AkShare是同步库）
_executor = ThreadPoolExecutor(max_workers=6)

# ---- 股票名称缓存 ----
_stock_cache: dict | None = None
_stock_cache_time: datetime | None = None


def _load_stock_cache() -> dict:
    """加载股票名称→代码映射（使用K线接口，比spot_em快很多）"""
    global _stock_cache, _stock_cache_time
    now = datetime.now()
    if _stock_cache and _stock_cache_time and (now - _stock_cache_time).seconds < 7200:
        return _stock_cache

    try:
        # 用个股列表接口（轻量）
        df = ak.stock_zh_a_spot_em()
        _stock_cache = {}
        for _, row in df.iterrows():
            code = str(row.get("代码", ""))
            name = str(row.get("名称", ""))
            if code and name:
                _stock_cache[name] = {"code": code, "price": row.get("最新价"),
                                       "pe": row.get("市盈率-动态"), "pb": row.get("市净率"),
                                       "mv": row.get("总市值"), "change": row.get("涨跌幅")}
                _stock_cache[code] = _stock_cache[name]
        _stock_cache_time = now
    except Exception:
        pass
    return _stock_cache or {}


def resolve_stock(query: str) -> tuple[str, str] | None:
    """
    用户输入→(代码, 名称)。
    核心原则：绝不阻塞。如果缓存没就绪，用快速备用方案。
    """
    query = query.strip()

    # 1. 优先用缓存（毫秒级）
    if _stock_cache:
        # 精确匹配
        if query in _stock_cache:
            info = _stock_cache[query]
            code = info["code"]
            name = query if not query.isdigit() else next(
                (k for k, v in _stock_cache.items() if isinstance(v, dict) and v.get("code") == code and not k.isdigit()), query
            )
            return (code, name)
        # 模糊匹配
        for key, info in _stock_cache.items():
            if isinstance(info, dict) and not key.isdigit() and query in key:
                return (info["code"], key)

    # 2. 缓存没就绪 → 快速备用方案（不等待，不阻塞）
    # 常见股票硬编码映射（覆盖最热门的50只）
    QUICK_MAP = {
        "贵州茅台": "600519", "茅台": "600519",
        "比亚迪": "002594", "宁德时代": "300750",
        "中国平安": "601318", "招商银行": "600036",
        "腾讯": "00700", "阿里巴巴": "09988",
        "工商银行": "601398", "建设银行": "601939",
        "中国银行": "601988", "农业银行": "601288",
        "中国中免": "601888", "美的集团": "000333",
        "格力电器": "000651", "海尔智家": "600690",
        "隆基绿能": "601012", "恒瑞医药": "600276",
        "药明康德": "603259", "迈瑞医疗": "300760",
        "五粮液": "000858", "泸州老窖": "000568",
        "长江电力": "600900", "中国神华": "601088",
        "紫金矿业": "601899", "中国石油": "601857",
        "中国移动": "600941", "中国电信": "601728",
        "立讯精密": "002475", "歌尔股份": "002241",
        "东方财富": "300059", "同花顺": "300033",
        "中信证券": "600030", "海天味业": "603288",
        "万科": "000002", "保利发展": "600048",
        "三一重工": "600031", "中联重科": "000157",
        "科大讯飞": "002230", "海康威视": "002415",
        "中芯国际": "688981", "韦尔股份": "603501",
    }
    for name, code in QUICK_MAP.items():
        if query in name or query == code:
            return (code, name)

    # 3. 如果输入看起来像股票代码（纯数字6位），直接用
    if query.isdigit() and len(query) == 6:
        return (query, query)

    # 4. 都匹配不上，返回None（让后续逻辑用用户原始输入搜索）
    return None


def _get_market(code: str) -> str:
    if code.startswith(("6", "9")):
        return "sh"
    elif code.startswith(("0", "3")):
        return "sz"
    return "bj"


# ---- 数据获取函数（同步，在线程池中执行）----

def _fetch_financials(code: str) -> list[dict] | None:
    """财报主要指标（限制2024年起，1-2秒）"""
    try:
        df = ak.stock_financial_analysis_indicator(symbol=code, start_year="2024")
        if df is not None and len(df) > 0:
            return df.head(4).to_dict(orient="records")
    except Exception:
        pass
    return None


def _fetch_realtime_from_cache(code: str) -> dict | None:
    """从缓存获取实时行情（如果缓存已加载）"""
    cache = _stock_cache or {}
    info = cache.get(code)
    if isinstance(info, dict):
        return info
    return None


def _fetch_price_history(code: str) -> list[dict] | None:
    """近60日K线（0.2秒）"""
    try:
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
        df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                 start_date=start, end_date=end, adjust="qfq")
        if df is not None and len(df) > 0:
            return df.tail(30).to_dict(orient="records")
    except Exception:
        pass
    return None


def _fetch_fund_flow(code: str) -> list[dict] | None:
    """个股资金流向（0.5秒）"""
    try:
        market = _get_market(code)
        df = ak.stock_individual_fund_flow(stock=code, market=market)
        if df is not None and len(df) > 0:
            return df.tail(10).to_dict(orient="records")
    except Exception:
        pass
    return None


def _fetch_valuation(code: str) -> dict | None:
    """估值指标+PE历史分位"""
    try:
        df = ak.stock_a_gxl_lg(symbol="上证A股")
        # 这个接口返回全市场，无法筛选个股
        # 改用缓存中的PE/PB
        return None
    except Exception:
        return None


def _fetch_news(code: str) -> list[dict] | None:
    """个股新闻（东方财富，0.7秒）"""
    try:
        df = ak.stock_news_em(symbol=code)
        if df is not None and len(df) > 0:
            return [
                {
                    "title": str(row.get("新闻标题", "")),
                    "content": str(row.get("新闻内容", ""))[:300],
                    "time": str(row.get("发布时间", "")),
                    "source": str(row.get("文章来源", "")),
                    "url": str(row.get("新闻链接", "")),
                }
                for _, row in df.head(8).iterrows()
            ]
    except Exception:
        pass
    return None


def _fetch_dividends(code: str) -> list[dict] | None:
    """历史分红"""
    try:
        df = ak.stock_history_dividend_detail(symbol=code, indicator="分红")
        if df is not None and len(df) > 0:
            return df.head(5).to_dict(orient="records")
    except Exception:
        pass
    return None


# ---- 异步并发获取 ----

async def get_stock_full_data(code: str) -> dict:
    """并发获取全维度数据"""
    loop = asyncio.get_event_loop()

    # 并发执行所有数据获取
    fin_task = loop.run_in_executor(_executor, _fetch_financials, code)
    price_task = loop.run_in_executor(_executor, _fetch_price_history, code)
    flow_task = loop.run_in_executor(_executor, _fetch_fund_flow, code)
    news_task = loop.run_in_executor(_executor, _fetch_news, code)
    div_task = loop.run_in_executor(_executor, _fetch_dividends, code)

    results = {}
    for key, task in [
        ("financials", fin_task),
        ("price_history", price_task),
        ("fund_flow", flow_task),
        ("news", news_task),
        ("dividends", div_task),
    ]:
        try:
            results[key] = await task
        except Exception:
            results[key] = None

    # 实时行情从缓存取（不额外请求）
    results["realtime"] = _fetch_realtime_from_cache(code)

    return results


# ---- 格式化 ----

def format_stock_data(data: dict, stock_name: str = "", stock_code: str = "") -> str:
    """格式化为LLM可读文本"""
    parts = []
    parts.append(f"=== {stock_name}({stock_code}) 东方财富结构化数据 ===")
    parts.append(f"数据获取时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    # 实时行情
    rt = data.get("realtime")
    if rt and isinstance(rt, dict):
        parts.append("【实时行情】")
        parts.append(f"最新价：{rt.get('price', 'N/A')} 元")
        parts.append(f"涨跌幅：{rt.get('change', 'N/A')}%")
        parts.append(f"市盈率(动态)：{rt.get('pe', 'N/A')} 倍")
        parts.append(f"市净率：{rt.get('pb', 'N/A')} 倍")
        parts.append(f"总市值：{rt.get('mv', 'N/A')}")
        parts.append("")

    # 财报
    fin = data.get("financials")
    if fin:
        parts.append("【财报主要指标（近4期）】")
        for row in fin:
            period = row.get("日期", "未知期")
            parts.append(f"\n--- 报告期：{period} ---")
            for key, val in row.items():
                if key != "日期" and val is not None and str(val).strip():
                    parts.append(f"  {key}：{val}")
        parts.append("")

    # 资金流向
    ff = data.get("fund_flow")
    if ff:
        parts.append("【个股资金流向（近期）】")
        for row in ff[-5:]:
            date = row.get("日期", "")
            main_in = row.get("主力净流入-净额", "N/A")
            main_pct = row.get("主力净流入-净占比", "N/A")
            big_in = row.get("超大单净流入-净额", "N/A")
            parts.append(f"  {date}：主力净流入{main_in}（占比{main_pct}%），超大单{big_in}")
        parts.append("")

    # K线
    ph = data.get("price_history")
    if ph:
        parts.append("【近期K线（近10日）】")
        for row in ph[-10:]:
            parts.append(f"  {row.get('日期','')}：开{row.get('开盘','')} 收{row.get('收盘','')} "
                         f"涨跌幅{row.get('涨跌幅','')}% 成交量{row.get('成交量','')} 换手率{row.get('换手率','')}%")
        parts.append("")

    # 新闻
    news = data.get("news")
    if news:
        parts.append("【个股新闻（东方财富）】")
        for i, n in enumerate(news[:5], 1):
            parts.append(f"  {i}. {n.get('title', '')} ({n.get('time', '')})")
            parts.append(f"     来源：{n.get('source', '')} | 链接：{n.get('url', '')}")
            content = n.get('content', '')
            if content:
                parts.append(f"     摘要：{content[:150]}")
        parts.append("")

    # 分红
    div = data.get("dividends")
    if div:
        parts.append("【历史分红记录】")
        for row in div:
            parts.append(f"  {row}")
        parts.append("")

    if len(parts) <= 3:
        parts.append("未获取到结构化数据。")

    return "\n".join(parts)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="获取A股个股全维度数据")
    parser.add_argument("--query", type=str, required=True, help="股票名称或代码，如 比亚迪 或 002594")
    args = parser.parse_args()

    # 先尝试加载缓存（可选，会使实时行情可用）
    print(f"正在查询：{args.query} ...", flush=True)
    _load_stock_cache()

    # 解析股票
    resolved = resolve_stock(args.query)
    if resolved:
        code, name = resolved
    else:
        print(f"未找到匹配的股票：{args.query}")
        exit(1)

    print(f"匹配到：{name}({code})，正在获取数据...", flush=True)

    # 获取全维度数据
    data = asyncio.run(get_stock_full_data(code))

    # 格式化输出
    output = format_stock_data(data, stock_name=name, stock_code=code)
    print(output)

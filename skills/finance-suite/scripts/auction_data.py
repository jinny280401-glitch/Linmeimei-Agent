"""
集合竞价排行榜 + 量化选股信号
数据源：东方财富（通过AkShare）

独立CLI脚本，无内部依赖
用法: python3 auction_data.py --query "集合竞价"
"""

import asyncio
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import akshare as ak

_executor = ThreadPoolExecutor(max_workers=4)


def _fetch_zt_pool(date: str = None) -> list[dict] | None:
    """涨停池（含封板资金、首次封板时间、连板数等）"""
    try:
        if not date:
            date = datetime.now().strftime("%Y%m%d")
        df = ak.stock_zt_pool_em(date=date)
        if df is not None and len(df) > 0:
            return df.to_dict(orient="records")
    except Exception:
        pass
    return None


def _fetch_strong_pool(date: str = None) -> list[dict] | None:
    """强势股池（涨停但未封死）"""
    try:
        if not date:
            date = datetime.now().strftime("%Y%m%d")
        df = ak.stock_zt_pool_strong_em(date=date)
        if df is not None and len(df) > 0:
            return df.to_dict(orient="records")
    except Exception:
        pass
    return None


def _fetch_previous_zt(date: str = None) -> list[dict] | None:
    """昨日涨停今日表现"""
    try:
        if not date:
            date = datetime.now().strftime("%Y%m%d")
        df = ak.stock_zt_pool_previous_em(date=date)
        if df is not None and len(df) > 0:
            return df.to_dict(orient="records")
    except Exception:
        pass
    return None


def _fetch_changes(symbol: str = "大笔买入") -> list[dict] | None:
    """盘中异动（大笔买入/大笔卖出/封涨停板/打开涨停板等）"""
    try:
        df = ak.stock_changes_em(symbol=symbol)
        if df is not None and len(df) > 0:
            return df.head(30).to_dict(orient="records")
    except Exception:
        pass
    return None


def _fetch_hot_rank() -> list[dict] | None:
    """东方财富人气排行榜"""
    try:
        df = ak.stock_hot_rank_em()
        if df is not None and len(df) > 0:
            return df.head(30).to_dict(orient="records")
    except Exception:
        pass
    return None


def _fetch_hot_up() -> list[dict] | None:
    """飙升榜（人气飙升最快的股票）"""
    try:
        df = ak.stock_hot_up_em()
        if df is not None and len(df) > 0:
            return df.head(20).to_dict(orient="records")
    except Exception:
        pass
    return None


def _fetch_spot_sorted() -> list[dict] | None:
    """全市场实时行情（按涨幅排序前50）"""
    try:
        df = ak.stock_zh_a_spot_em()
        if df is not None and len(df) > 0:
            items = []
            for _, row in df.iterrows():
                code = str(row.get("代码", ""))
                name = str(row.get("名称", ""))
                if code and name:
                    items.append({
                        "name": name,
                        "code": code,
                        "price": row.get("最新价"),
                        "change": row.get("涨跌幅"),
                        "pe": row.get("市盈率-动态"),
                        "mv": row.get("总市值"),
                    })
            by_change = sorted(items, key=lambda x: float(x.get("change") or 0), reverse=True)[:50]
            return by_change
    except Exception:
        pass
    return None


async def get_auction_data() -> dict:
    """并发获取集合竞价相关全部数据"""
    loop = asyncio.get_event_loop()

    tasks = {
        "zt_pool": loop.run_in_executor(_executor, _fetch_zt_pool, None),
        "strong_pool": loop.run_in_executor(_executor, _fetch_strong_pool, None),
        "previous_zt": loop.run_in_executor(_executor, _fetch_previous_zt, None),
        "big_buy": loop.run_in_executor(_executor, _fetch_changes, "大笔买入"),
        "hot_rank": loop.run_in_executor(_executor, _fetch_hot_rank),
        "hot_up": loop.run_in_executor(_executor, _fetch_hot_up),
    }

    results = {}
    for key, task in tasks.items():
        try:
            results[key] = await task
        except Exception:
            results[key] = None

    # 获取涨幅排行（独立获取，不再依赖stock_data缓存）
    results["top_gainers"] = _fetch_spot_sorted()

    return results


def format_auction_data(data: dict) -> str:
    """格式化为LLM可读文本"""
    parts = []
    parts.append(f"=== 集合竞价与盘面数据（东方财富）===")
    parts.append(f"数据时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    # 涨停池
    zt = data.get("zt_pool")
    if zt:
        parts.append(f"【今日涨停池】共{len(zt)}只")
        for s in zt[:15]:
            parts.append(f"  {s.get('名称','')}({s.get('代码','')}) "
                        f"涨幅{s.get('涨跌幅','')}% 成交额{s.get('成交额','')} "
                        f"封板资金{s.get('封板资金','')} "
                        f"首封{s.get('首次封板时间','')} 连板{s.get('连板数','')}")
        parts.append("")

    # 强势股
    strong = data.get("strong_pool")
    if strong:
        parts.append(f"【强势股池】共{len(strong)}只")
        for s in strong[:10]:
            parts.append(f"  {s}")
        parts.append("")

    # 昨日涨停今日表现
    prev = data.get("previous_zt")
    if prev:
        parts.append(f"【昨日涨停今日表现】共{len(prev)}只")
        for s in prev[:10]:
            parts.append(f"  {s}")
        parts.append("")

    # 大笔买入异动
    bb = data.get("big_buy")
    if bb:
        parts.append(f"【盘中大笔买入异动】共{len(bb)}条")
        for s in bb[:15]:
            parts.append(f"  {s.get('时间','')} {s.get('名称','')}({s.get('代码','')}) "
                        f"板块:{s.get('板块','')} {s.get('相关信息','')}")
        parts.append("")

    # 热门排行
    hot = data.get("hot_rank")
    if hot:
        parts.append(f"【东方财富人气排行Top20】")
        for i, s in enumerate(hot[:20], 1):
            parts.append(f"  {i}. {s}")
        parts.append("")

    # 飙升榜
    up = data.get("hot_up")
    if up:
        parts.append(f"【人气飙升榜Top10】")
        for i, s in enumerate(up[:10], 1):
            parts.append(f"  {i}. {s}")
        parts.append("")

    # 涨幅排行
    gainers = data.get("top_gainers")
    if gainers:
        parts.append(f"【涨幅排行Top20】")
        for i, s in enumerate(gainers[:20], 1):
            parts.append(f"  {i}. {s.get('name','')}({s.get('code','')}) "
                        f"涨幅{s.get('change','')}% 最新价{s.get('price','')} PE{s.get('pe','')}")
        parts.append("")

    if len(parts) <= 3:
        parts.append("当前非交易时段或数据暂不可用。")

    return "\n".join(parts)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="获取集合竞价与盘面数据")
    parser.add_argument("--query", type=str, default="集合竞价", help="查询内容（当前忽略，获取全部盘面数据）")
    args = parser.parse_args()

    print("正在获取集合竞价与盘面数据...", flush=True)

    data = asyncio.run(get_auction_data())
    output = format_auction_data(data)
    print(output)

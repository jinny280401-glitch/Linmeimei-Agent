"""
AkShare 宏观经济数据获取模块
通过国家统计局/央行等数据源获取宏观经济结构化数据
所有函数经过验证，参数与AkShare 1.18.48一致

独立CLI脚本，无内部依赖
用法: python3 macro_data.py --query "宏观经济"
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import akshare as ak

_executor = ThreadPoolExecutor(max_workers=4)


def _fetch_gdp():
    """GDP数据"""
    try:
        df = ak.macro_china_gdp()
        return df.tail(8).to_dict(orient="records")
    except Exception:
        return None


def _fetch_cpi():
    """CPI数据"""
    try:
        df = ak.macro_china_cpi_monthly()
        return df.tail(12).to_dict(orient="records")
    except Exception:
        return None


def _fetch_pmi():
    """PMI数据"""
    try:
        df = ak.macro_china_pmi()
        return df.tail(12).to_dict(orient="records")
    except Exception:
        return None


def _fetch_money_supply():
    """M2货币供应"""
    try:
        df = ak.macro_china_money_supply()
        return df.tail(12).to_dict(orient="records")
    except Exception:
        return None


def _fetch_lpr():
    """LPR利率"""
    try:
        df = ak.macro_china_lpr()
        return df.tail(12).to_dict(orient="records")
    except Exception:
        return None


def _fetch_shibor():
    """SHIBOR利率"""
    try:
        df = ak.rate_interbank(
            market="上海银行间同业拆放利率(Shibor)",
            symbol="隔夜",
            need_page="1",
        )
        return df.tail(30).to_dict(orient="records")
    except Exception:
        return None


async def get_macro_data() -> dict:
    """并发获取所有宏观经济数据"""
    loop = asyncio.get_event_loop()
    tasks = {
        "gdp": loop.run_in_executor(_executor, _fetch_gdp),
        "cpi": loop.run_in_executor(_executor, _fetch_cpi),
        "pmi": loop.run_in_executor(_executor, _fetch_pmi),
        "money_supply": loop.run_in_executor(_executor, _fetch_money_supply),
        "lpr": loop.run_in_executor(_executor, _fetch_lpr),
    }
    results = {}
    for key, task in tasks.items():
        try:
            results[key] = await task
        except Exception:
            results[key] = None
    return results


def format_macro_data(data: dict) -> str:
    """格式化宏观数据为文本"""
    parts = ["=== 宏观经济结构化数据（来源：国家统计局/央行）===\n"]
    for key, records in data.items():
        if records:
            parts.append(f"【{key.upper()}】")
            for r in records[-6:]:
                parts.append(f"  {r}")
            parts.append("")
    return "\n".join(parts)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="获取宏观经济数据（GDP/CPI/PMI/M2/LPR）")
    parser.add_argument("--query", type=str, default="宏观经济", help="查询内容（当前忽略，获取全部宏观数据）")
    args = parser.parse_args()

    print("正在获取宏观经济数据...", flush=True)

    data = asyncio.run(get_macro_data())
    output = format_macro_data(data)
    print(output)

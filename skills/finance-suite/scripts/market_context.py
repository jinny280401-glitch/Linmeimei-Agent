"""
Market Context Layer / 今日市场画像

只读聚合层：基于现有 auction_data 取数结果生成市场结构摘要。
不写数据库，不改变登录和集合竞价逻辑。
"""

from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime
from typing import Any

import auction_data

INSUFFICIENT_TEXT = "数据不足，暂不下结论"


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("%", "").replace(",", "")
    if not text or text in {"-", "--", "nan", "None"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_int(value: Any) -> int:
    number = _to_float(value)
    return int(number) if number is not None else 0


def _pick(item: dict, *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, "", "--"):
            return value
    return default


def _format_amount(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return ""
    abs_number = abs(number)
    if abs_number >= 100_000_000:
        return f"{number / 100_000_000:.1f} 亿"
    if abs_number >= 10_000:
        return f"{number / 10_000:.0f} 万"
    return f"{number:.0f}"


def _stock(item: dict) -> dict:
    turnover = _pick(item, "成交额", "成交金额", "amount", default=None)
    sealed_amount = _pick(item, "封板资金", "封单金额", default=None)
    return {
        "name": str(_pick(item, "名称", "name", default="")),
        "code": str(_pick(item, "代码", "code", default="")),
        "sector": str(_pick(item, "所属行业", "行业", "板块", "sector", default="")),
        "change_pct": _to_float(_pick(item, "涨跌幅", "change", default=None)),
        "turnover": _format_amount(turnover),
        "sealed_amount": _format_amount(sealed_amount),
        "streak": _to_int(_pick(item, "连板数", "streak", default=0)),
    }


def _top_sectors(items: list[dict], limit: int = 5) -> list[dict]:
    counter: Counter[str] = Counter()
    for item in items:
        sector = str(_pick(item, "所属行业", "行业", "板块", "sector", default="")).strip()
        if sector:
            counter[sector] += 1
    total = len(items) or 1
    return [
        {"name": name, "count": count, "share": round(count / total, 4)}
        for name, count in counter.most_common(limit)
    ]


def _average(values: list[float]) -> float | None:
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return round(sum(valid) / len(valid), 2)


def _qc(data: dict, summary: dict) -> dict:
    dimensions = {
        "zt_pool": data.get("zt_pool"),
        "strong_pool": data.get("strong_pool"),
        "previous_zt": data.get("previous_zt"),
        "hot_rank": data.get("hot_rank"),
        "top_gainers": data.get("top_gainers"),
    }
    missing = [key for key, value in dimensions.items() if not value]
    present = len(dimensions) - len(missing)
    completeness = round(present / len(dimensions), 2)
    status = "success" if completeness >= 0.8 else ("partial" if completeness > 0 else "failure")
    if summary.get("conclusion") == INSUFFICIENT_TEXT:
        status = "partial" if completeness > 0 else "failure"
    return {
        "status": status,
        "completeness": completeness,
        "sources": ["akshare"] if present else [],
        "fallback_source": None,
        "missing_dimensions": missing,
        "stale_data": [],
    }


def build_context(data: dict | None = None) -> dict:
    data = data or {}
    zt_pool = data.get("zt_pool") or []
    strong_pool = data.get("strong_pool") or []
    previous_zt = data.get("previous_zt") or []
    top_gainers = data.get("top_gainers") or []

    zt_items = [_stock(item) for item in zt_pool if isinstance(item, dict)]
    prev_changes = [
        _to_float(_pick(item, "涨跌幅", "change", default=None))
        for item in previous_zt
        if isinstance(item, dict)
    ]
    prev_changes = [v for v in prev_changes if v is not None]

    highest_streak = max([item["streak"] for item in zt_items] or [0])
    streak_samples = [item for item in zt_items if item["streak"] >= 2]
    large_turnover = [_stock(item) for item in top_gainers[:20] if isinstance(item, dict)]
    sectors = _top_sectors(zt_pool)

    zt_count = len(zt_pool)
    strong_count = len(strong_pool)
    open_ratio = round(strong_count / (zt_count + strong_count) * 100, 1) if zt_count + strong_count else None
    prev_avg = _average(prev_changes)
    prev_positive_ratio = round(len([v for v in prev_changes if v > 0]) / len(prev_changes) * 100, 1) if prev_changes else None
    continuation_rate = round(len([item for item in zt_items if item["streak"] >= 2]) / zt_count * 100, 1) if zt_count else None

    enough = bool(zt_pool and (previous_zt or top_gainers))
    top_sector = sectors[0] if sectors else None
    if not enough:
        conclusion = INSUFFICIENT_TEXT
        preference = INSUFFICIENT_TEXT
        concentration = INSUFFICIENT_TEXT
        breadth = INSUFFICIENT_TEXT
    else:
        concentration = "高" if top_sector and top_sector["share"] >= 0.25 else ("中" if top_sector and top_sector["share"] >= 0.15 else "分散")
        preference = "偏活跃" if zt_count >= 80 else ("中性" if zt_count >= 40 else "偏弱")
        breadth = "集中于主线" if concentration == "高" else ("多方向扩散" if concentration == "分散" else "适中")
        conclusion = f"{top_sector['name']}集中度较高" if top_sector and top_sector["share"] >= 0.2 else "市场结构分布相对分散"

    payload = {
        "title": "今日市场画像",
        "positioning": "市场结构摘要 / Market Context Layer",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "date_label": datetime.now().strftime("%Y-%m-%d"),
        "conclusion": conclusion,
        "metrics": {
            "limit_up_count": zt_count if zt_pool else None,
            "open_board_ratio": open_ratio,
            "previous_limit_avg_change_pct": prev_avg,
            "previous_limit_positive_ratio": prev_positive_ratio,
            "continuation_rate": continuation_rate,
            "highest_streak": highest_streak if highest_streak else None,
        },
        "context": {
            "market_preference": preference,
            "theme_concentration": concentration,
            "breadth": breadth,
            "top_sector": top_sector,
        },
        "themes": sectors,
        "roles": {
            "streak_samples": sorted(streak_samples, key=lambda x: x["streak"], reverse=True)[:5],
            "large_turnover_samples": large_turnover[:5],
            "high_change_samples": large_turnover[:5],
        },
        "monitoring": [
            "开板比例持续抬升，说明市场分歧加大",
            "昨日涨停样本平均表现转弱，说明短线承接下降",
            "主线集中度明显下降，说明结构正在扩散或切换",
        ] if enough else [INSUFFICIENT_TEXT],
        "disclaimer": "本页面呈现市场结构数据，不含操作建议。仅供参考，不构成投资建议。",
    }
    payload["_qc"] = _qc(data, payload)
    return payload


async def snapshot() -> dict:
    data = await auction_data.get_auction_data()
    return build_context(data)


def snapshot_sync() -> dict:
    return asyncio.run(snapshot())

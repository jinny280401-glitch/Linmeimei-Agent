"""
market_intel Sidebar 统一数据契约 (v1)

所有 Sidebar 板块返回值都遵循同一顶层结构，便于前端通用渲染：

顶层 envelope:
{
  "items": [Item, ...],
  "_qc": { status, completeness, sources, fallback_source, ... },
  "meta": { module, ts, count, ... }
}

每条 Item 必备字段:
{
  "id":     str         去重/联动主键
  "type":   str         "discussion" | "hot_stock" | "watch_alert" | "research"
  "title":  str         展示标题（一行能放下）
  "ts":     str         ISO8601；缺失时回退到拉取时间
  "stocks": [           关联股票，用于点击联动 stock_analysis
              { "code": str, "name": str, "market": "SH"|"SZ"|"BJ"|"HK"|"US"|"" }
            ]
  "tags":   [str]       行业/主题标签，用于行业联动
  "href":   str|None    原文链接（PDF/帖子/无则 None）
  "extra":  dict        板块专属字段（不污染顶层）
}

extra 各板块约定（v1 列出常见键，前端可宽容缺失）:
  - discussion : { heat, source }                      雪球热门 / 知乎热榜 / 新浪快讯
  - hot_stock  : { change, price, turnover, rank }     涨幅 / 价格 / 排名
  - watch_alert: { alert_type, threshold, current }    above/below/change_pct
  - research   : { broker, rating, rating_change, target_price,
                   core_logic, catalysts, risks, digest_status }
                 digest_status: "pending" | "batch" | "deep"
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Iterable


MODULES = ("discussions", "hot_stocks", "watch_alerts", "research")


def make_item(
    *,
    id: str,
    type: str,
    title: str,
    ts: str | None = None,
    stocks: list[dict] | None = None,
    tags: list[str] | None = None,
    href: str | None = None,
    extra: dict | None = None,
) -> dict:
    """构造一条标准 item，保证字段齐全。"""
    return {
        "id": id,
        "type": type,
        "title": title,
        "ts": ts or datetime.now().isoformat(timespec="seconds"),
        "stocks": stocks or [],
        "tags": tags or [],
        "href": href,
        "extra": extra or {},
    }


def make_stock_ref(code: str, name: str = "", market: str = "") -> dict:
    """构造一个 stocks[] 子项，统一字段。"""
    return {"code": code, "name": name, "market": market}


def envelope(
    *,
    module: str,
    items: list[dict],
    qc: dict,
    extra_meta: dict | None = None,
) -> dict:
    """打包成最终顶层 envelope。"""
    meta = {
        "module": module,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "count": len(items),
    }
    if extra_meta:
        meta.update(extra_meta)
    return {"items": items, "_qc": qc, "meta": meta}


def empty_qc(reason: str = "no data") -> dict:
    return {
        "status": "failure",
        "completeness": 0.0,
        "sources": [],
        "fallback_source": None,
        "missing_dimensions": ["items"],
        "stale_data": [],
        "error": reason,
    }


def simple_qc(
    *,
    items: Iterable[Any],
    sources: list[str],
    fallback_source: str | None = None,
    expected: int = 5,
) -> dict:
    """按条目数粗算 completeness，给通用聚合工具用。"""
    count = sum(1 for _ in items)
    if count == 0:
        return {
            "status": "failure",
            "completeness": 0.0,
            "sources": [],
            "fallback_source": fallback_source,
            "missing_dimensions": ["items"],
            "stale_data": [],
        }
    completeness = min(1.0, round(count / max(expected, 1), 2))
    return {
        "status": "success" if completeness >= 0.6 else "partial",
        "completeness": completeness,
        "sources": sources,
        "fallback_source": fallback_source,
        "missing_dimensions": [],
        "stale_data": [],
    }

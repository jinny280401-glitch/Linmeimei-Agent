"""
market_intel.py — Sidebar 一键聚合工具

把四个板块按统一契约打包：
  discussions  雪球热门 + 知乎热榜 + 新浪快讯（autocli 任一可用即返回）
  hot_stocks   market_pulse 涨停/人气榜 → 转契约
  watch_alerts watchlist monitor → 转契约
  research     research_digest.latest()

设计：
- 任一板块失败不阻塞其他板块；
- 各板块独立 _qc，顶层有 aggregate _qc 反映整体状态；
- v1 串行简单可靠（每个板块自带 timeout/降级），并发交给 v2。
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from typing import Any

from market_intel_schema import envelope, make_item, make_stock_ref, simple_qc

logger = logging.getLogger("finance-suite.market_intel")

_AUTOCLI = os.path.expanduser("~/bin/autocli")


# ---------- helpers ----------

def _autocli_json(platform: str, subcmd: list[str], *, timeout: int = 25) -> tuple[bool, Any, str]:
    if not os.path.exists(_AUTOCLI):
        return False, None, "autocli 未安装"
    cmd = [_AUTOCLI, platform] + subcmd + ["--format", "json"]
    env = os.environ.copy()
    env["NO_PROXY"] = "localhost,127.0.0.1"
    env["no_proxy"] = "localhost,127.0.0.1"
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        if r.returncode != 0:
            return False, None, (r.stderr or r.stdout or "").strip()[:200]
        return True, json.loads(r.stdout.strip()), ""
    except subprocess.TimeoutExpired:
        return False, None, f"timeout {timeout}s"
    except json.JSONDecodeError as e:
        return False, None, f"json decode: {e}"
    except Exception as e:
        return False, None, str(e)


def _stable_id(*parts: str) -> str:
    import hashlib
    return hashlib.sha1("|".join(p or "" for p in parts).encode("utf-8")).hexdigest()[:16]


def _market_of(code: str) -> str:
    if not code:
        return ""
    code = code.upper()
    if code.startswith(("SH", "SZ", "BJ")):
        return code[:2]
    head = re.sub(r"[^0-9]", "", code)[:3]
    if head in ("600", "601", "603", "605", "688", "689", "900"):
        return "SH"
    if head in ("000", "001", "002", "003", "300", "301", "200"):
        return "SZ"
    if head[:2] in ("43", "83", "87"):
        return "BJ"
    return ""


def _digit_code(code: str) -> str:
    return re.sub(r"[^0-9]", "", code or "")[:6]


def _xueqiu_stock_href(code: str) -> str | None:
    digits = _digit_code(code)
    if len(digits) != 6:
        return None
    market = _market_of(code)
    if not market:
        return None
    return f"https://xueqiu.com/S/{market}{digits}"


# ---------- discussions ----------

def discussions(*, limit: int = 10) -> dict:
    items: list[dict] = []
    sources_used: list[str] = []
    warnings: list[str] = []

    # 雪球热门
    ok, data, err = _autocli_json("xueqiu", ["hot", "--limit", str(limit)])
    if ok and isinstance(data, list):
        sources_used.append("xueqiu")
        for i, x in enumerate(data[:limit]):
            title = (x.get("title") or x.get("text") or x.get("description") or "").strip()
            if not title:
                continue
            heat = str(x.get("heat") or x.get("read_count") or x.get("retweet_count") or "")
            url = x.get("target") or x.get("url") or ""
            items.append(make_item(
                id=_stable_id("xq", title, str(i)),
                type="discussion",
                title=title[:120],
                stocks=[],
                tags=["雪球"],
                href=url or None,
                extra={"source": "雪球", "heat": heat},
            ))
    elif err:
        warnings.append(f"xueqiu: {err}")

    # 知乎热榜（财经过滤暂时不做，量小）
    if len(items) < limit:
        ok, data, err = _autocli_json("zhihu", ["hot", "--limit", str(limit)])
        if ok and isinstance(data, list):
            sources_used.append("zhihu")
            for i, x in enumerate(data[: max(0, limit - len(items))]):
                title = (x.get("title") or x.get("question") or "").strip()
                if not title:
                    continue
                heat = str(x.get("heat") or x.get("hot_value") or "")
                url = x.get("url") or x.get("target") or ""
                items.append(make_item(
                    id=_stable_id("zh", title, str(i)),
                    type="discussion",
                    title=title[:120],
                    tags=["知乎"],
                    href=url or None,
                    extra={"source": "知乎", "heat": heat},
                ))
        elif err:
            warnings.append(f"zhihu: {err}")

    # 新浪 7x24（兜底永远在线）
    if len(items) < limit:
        ok, data, err = _autocli_json("sinafinance", ["news", "--limit", str(limit)])
        if ok and isinstance(data, list):
            sources_used.append("sinafinance")
            for i, x in enumerate(data[: max(0, limit - len(items))]):
                title = (x.get("rich_text") or x.get("content") or x.get("title") or "").strip()
                if not title:
                    continue
                items.append(make_item(
                    id=_stable_id("sina", title, str(i)),
                    type="discussion",
                    title=title[:120],
                    ts=x.get("create_time") or x.get("ctime") or None,
                    tags=["快讯"],
                    href=x.get("url") or None,
                    extra={"source": "新浪7x24", "heat": ""},
                ))
        elif err:
            warnings.append(f"sina: {err}")

    qc = simple_qc(items=items, sources=sources_used, expected=min(5, limit))
    if warnings:
        qc["warnings"] = warnings
    return envelope(module="discussions", items=items, qc=qc)


# ---------- hot_stocks ----------

def _format_change(val: Any) -> str:
    try:
        f = float(val)
        return f"{f:+.2f}%"
    except (TypeError, ValueError):
        return str(val) if val not in (None, "") else ""


def hot_stocks(*, limit: int = 10) -> dict:
    """用 auction_data 的人气榜 / 涨幅榜做热股榜。"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import auction_data
        import asyncio
        data = asyncio.run(auction_data.get_auction_data())
    except Exception as e:
        return envelope(
            module="hot_stocks", items=[],
            qc={"status": "failure", "completeness": 0, "sources": [], "fallback_source": "akshare",
                "missing_dimensions": ["hot_stocks"], "stale_data": [], "error": str(e)},
        )

    pool = data.get("hot_rank") or data.get("top_gainers") or data.get("hot_up") or data.get("zt_pool") or []
    if not isinstance(pool, list):
        pool = []
    pool = pool[:limit]

    items: list[dict] = []
    for i, s in enumerate(pool):
        # akshare 字段：代码 / 名称 / 涨跌幅 / 最新价 / 排名
        code = str(s.get("代码") or s.get("code") or "").strip()
        name = str(s.get("名称") or s.get("name") or "").strip()
        change = _format_change(s.get("涨跌幅") or s.get("change_pct") or s.get("change"))
        price = s.get("最新价") or s.get("price") or ""
        rank = s.get("排名") or s.get("rank") or i + 1
        if not code:
            continue
        items.append(make_item(
            id=_stable_id("hot", code, str(i)),
            type="hot_stock",
            title=f"{name} {code}",
            stocks=[make_stock_ref(code=code, name=name, market=_market_of(code))],
            tags=[],
            href=_xueqiu_stock_href(code),
            extra={
                "rank": rank,
                "change": change,
                "price": price,
            },
        ))

    qc = simple_qc(items=items, sources=["eastmoney"] if items else [], expected=min(5, limit))
    return envelope(module="hot_stocks", items=items, qc=qc)


# ---------- watch_alerts ----------

def watch_alerts(*, change_threshold: float = 3.0) -> dict:
    """直接调 watchlist.action_monitor 抓最新一次行情，按 alerts/价格变化抽出 item。"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import io
        from contextlib import redirect_stdout
        import watchlist as wl

        class A:
            pass

        buf = io.StringIO()
        with redirect_stdout(buf):
            wl.action_monitor(A())
        try:
            data = json.loads(buf.getvalue())
        except json.JSONDecodeError:
            data = {}
    except Exception as e:
        return envelope(
            module="watch_alerts", items=[],
            qc={"status": "failure", "completeness": 0, "sources": [], "fallback_source": None,
                "missing_dimensions": ["watch_alerts"], "stale_data": [], "error": str(e)},
        )

    items: list[dict] = []
    stocks = data.get("stocks") or []
    triggered = data.get("alerts_triggered") or []

    for s in stocks:
        change_pct = s.get("change_pct")
        if change_pct is None:
            continue
        try:
            cp = float(change_pct)
        except (TypeError, ValueError):
            continue
        if abs(cp) < change_threshold:
            continue
        code = str(s.get("code", ""))
        name = s.get("name", "")
        items.append(make_item(
            id=_stable_id("alert", code, str(int(time.time() // 60))),
            type="watch_alert",
            title=f"{name} {('+' if cp>=0 else '')}{cp:.2f}%",
            stocks=[make_stock_ref(code=code, name=name, market=_market_of(code))],
            tags=s.get("tags") or [],
            extra={
                "alert_type": "rise" if cp >= 0 else "drop",
                "change_pct": cp,
                "price": s.get("price"),
                "pnl_pct": s.get("pnl_pct"),
                "threshold": change_threshold,
            },
        ))

    # 已触发的提醒条目（来自 alerts 配置）
    for i, msg in enumerate(triggered):
        items.append(make_item(
            id=_stable_id("alert_cfg", msg, str(i)),
            type="watch_alert",
            title=msg,
            tags=["阈值"],
            extra={"alert_type": "configured", "raw": msg},
        ))

    qc = simple_qc(items=items, sources=["watchlist"] if stocks else [], expected=1)
    qc.setdefault("missing_dimensions", [])
    if not stocks:
        qc["status"] = "partial" if not items else qc["status"]
        qc["note"] = "自选清单为空或行情失败"
    return envelope(
        module="watch_alerts", items=items, qc=qc,
        extra_meta={"watch_count": len(stocks), "alerted_count": len(items)},
    )


# ---------- research ----------

def research(*, limit: int = 10, digest_mode: str = "batch", max_llm: int = 4) -> dict:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import research_digest as rd
    return rd.latest(limit=limit, digest_mode=digest_mode, max_llm_per_call=max_llm)


# ---------- top-level ----------

_MODULE_FN = {
    "discussions": discussions,
    "hot_stocks": hot_stocks,
    "watch_alerts": watch_alerts,
    "research": research,
}


def aggregate(modules: list[str] | None = None, *, limit: int = 10, digest_mode: str = "batch") -> dict:
    """一次拉所有板块。"""
    modules = modules or list(_MODULE_FN.keys())
    panels: dict[str, dict] = {}
    statuses: list[str] = []
    sources: set[str] = set()

    for m in modules:
        fn = _MODULE_FN.get(m)
        if not fn:
            continue
        try:
            if m == "research":
                p = fn(limit=limit, digest_mode=digest_mode, max_llm=4)
            elif m == "watch_alerts":
                p = fn()
            else:
                p = fn(limit=limit)
        except Exception as e:
            logger.exception(f"module {m} failed")
            p = envelope(
                module=m, items=[],
                qc={"status": "failure", "completeness": 0, "sources": [], "fallback_source": None,
                    "missing_dimensions": [m], "stale_data": [], "error": str(e)},
            )
        panels[m] = p
        statuses.append(p["_qc"]["status"])
        for s in p["_qc"].get("sources") or []:
            sources.add(s)

    if all(s == "success" for s in statuses) and statuses:
        agg_status = "success"
    elif any(s in ("success", "partial") for s in statuses):
        agg_status = "partial"
    else:
        agg_status = "failure"

    agg_qc = {
        "status": agg_status,
        "completeness": round(
            sum(p["_qc"].get("completeness", 0) for p in panels.values()) / max(len(panels), 1), 2
        ),
        "sources": sorted(sources),
        "fallback_source": None,
        "missing_dimensions": [m for m, p in panels.items() if p["_qc"]["status"] == "failure"],
        "stale_data": [],
    }

    return {
        "panels": panels,
        "_qc": agg_qc,
        "meta": {
            "modules": list(panels.keys()),
            "ts": datetime.now().isoformat(timespec="seconds"),
            "limit": limit,
        },
    }


# ---------- CLI ----------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["all", "discussions", "hot_stocks", "watch_alerts", "research"])
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--mode", default="batch")
    args = parser.parse_args()

    if args.action == "all":
        out = aggregate(limit=args.limit, digest_mode=args.mode)
    elif args.action == "research":
        out = research(limit=args.limit, digest_mode=args.mode)
    elif args.action == "watch_alerts":
        out = watch_alerts()
    else:
        out = _MODULE_FN[args.action](limit=args.limit)

    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))

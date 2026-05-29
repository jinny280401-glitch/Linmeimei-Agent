"""
research_digest.py — A 股卖方研报批量脱水

定位：补 research_reports（海外投行精选）的另一面，做 A 股卖方研报的批量脱水。

数据流：
  东方财富研报中心 reportapi.eastmoney.com  (主源)
  AkShare stock_research_report_em        (个股维度降级 / 单只标的查询)
  ↓
  去重 (sha1(title_norm + first_stock + yyyymmdd))
  ↓
  SQLite 缓存 ~/.finance-suite/research_digest.db
  ↓
  LLM 脱水 (Haiku 批量 / Sonnet 深度)，无 key 时规则化 fallback
  ↓
  market_intel_schema 契约 envelope

action:
  latest      —— 全市场最新研报（默认 30 条）
  by_stock    —— 单股研报（穿透到 AkShare）
  by_industry —— 行业研报（按 industry 字符串过滤 latest）
  by_keyword  —— 标题关键词搜索（latest 之上做过滤）
  digest_one  —— 单篇深度脱水（mode=deep）

设计原则：
- LLM 为可选项，缺 API key 不阻塞；
- v1 不做 PDF 全文抓取，只用列表页结构化字段做脱水（足够 Sidebar 展示）；
- _qc 字段贴合 mcp_server 现有风格；
- dedup_key 用 sha1(标题归一 + 首只股票 + yyyymmdd)，可解释、低成本。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from market_intel_schema import envelope, make_item, make_stock_ref, simple_qc

logger = logging.getLogger("finance-suite.research_digest")

# ---------- 常量 ----------

_DB_PATH = Path.home() / ".finance-suite" / "research_digest.db"
_CACHE_TTL_SEC = 30 * 60  # latest 列表 30 分钟内不重拉
_EM_LIST_URL = "https://reportapi.eastmoney.com/report/list"
_PDF_URL_TPL = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"

# 评级 code → 中文（东方财富）
_RATING_NAME = {
    "001": "—",
    "002": "中性",
    "003": "减持",
    "004": "卖出",
    "005": "推荐",
    "006": "强推",
    "007": "买入",
    "008": "增持",
    "009": "审慎推荐",
    "010": "谨慎推荐",
}

# 评级变动 code（emRatingValue / lastEmRatingValue 间）
_RATING_CHANGE_TXT = {
    -2: "下调",
    -1: "下调",
    0: "维持",
    1: "上调",
    2: "上调",
}


# ---------- SQLite ----------

def _ensure_db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
            dedup_key      TEXT PRIMARY KEY,
            info_code      TEXT,
            title          TEXT,
            stock_code     TEXT,
            stock_name     TEXT,
            industry       TEXT,
            broker         TEXT,
            rating         TEXT,
            rating_change  TEXT,
            target_price   TEXT,
            eps_forecast   TEXT,
            publish_date   TEXT,
            pdf_url        TEXT,
            raw_json       TEXT,
            digest_json    TEXT,
            digest_engine  TEXT,
            fetched_at     INTEGER,
            digested_at    INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fetch_log (
            scope       TEXT PRIMARY KEY,
            last_run    INTEGER,
            last_count  INTEGER,
            last_source TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_publish ON reports(publish_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stock ON reports(stock_code)")
    conn.commit()
    return conn


def _last_fetch_ts(conn: sqlite3.Connection, scope: str) -> int:
    row = conn.execute(
        "SELECT last_run FROM fetch_log WHERE scope = ?", (scope,)
    ).fetchone()
    return row[0] if row else 0


def _record_fetch(conn: sqlite3.Connection, scope: str, count: int, source: str) -> None:
    conn.execute(
        "INSERT INTO fetch_log(scope, last_run, last_count, last_source) "
        "VALUES(?,?,?,?) ON CONFLICT(scope) DO UPDATE SET "
        "last_run=excluded.last_run, last_count=excluded.last_count, last_source=excluded.last_source",
        (scope, int(time.time()), count, source),
    )
    conn.commit()


# ---------- 工具函数 ----------

_TITLE_NORM_RE = re.compile(r"[\s\W_]+", re.UNICODE)


def _normalize_title(title: str) -> str:
    return _TITLE_NORM_RE.sub("", (title or "").lower())


def _dedup_key(title: str, stock_code: str, publish_date: str) -> str:
    norm_title = _normalize_title(title)
    date_only = (publish_date or "")[:10].replace("-", "")
    raw = f"{norm_title}|{stock_code or ''}|{date_only}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _to_market(stock_code: str) -> str:
    if not stock_code or len(stock_code) < 6:
        return ""
    head = stock_code[:3]
    if head in ("600", "601", "603", "605", "688", "689", "900"):
        return "SH"
    if head in ("000", "001", "002", "003", "300", "301", "200"):
        return "SZ"
    if head in ("430", "830", "831", "832", "833", "834", "835", "836", "837", "838", "839", "870", "871", "872", "873"):
        return "BJ"
    return ""


def _fmt_num(v: Any) -> str:
    """0.7300000000 → 0.73；非数字原样返回。"""
    try:
        f = float(v)
        s = f"{f:.4f}".rstrip("0").rstrip(".")
        return s if s else "0"
    except (TypeError, ValueError):
        return str(v)


def _rating_change(curr: str, last: str, change_field: int | str | None) -> str:
    """优先看 ratingChange 数值字段，否则比对前后评级。"""
    try:
        change = int(change_field) if change_field not in (None, "") else None
    except (TypeError, ValueError):
        change = None
    if change is not None:
        return _RATING_CHANGE_TXT.get(max(-2, min(2, change)), "维持")
    if not last or last == curr:
        return "维持"
    try:
        c, l = int(curr or 0), int(last or 0)
        if c > l:
            return "上调"
        if c < l:
            return "下调"
    except ValueError:
        pass
    return "维持"


# ---------- 数据源：东方财富 ----------

def _fetch_eastmoney(
    *,
    page_size: int = 50,
    days: int = 7,
    industry_code: str = "*",
    rating: str = "*",
    timeout: int = 10,
) -> tuple[list[dict], str | None]:
    """拉东方财富研报列表。返回 (raw_items, error)。"""
    end = datetime.now().date()
    begin = end - timedelta(days=days)
    params = {
        "industryCode": industry_code,
        "pageSize": page_size,
        "industry": "*",
        "rating": rating,
        "ratingChange": "*",
        "beginTime": begin.isoformat(),
        "endTime": end.isoformat(),
        "pageNo": 1,
        "fields": "",
        "qType": 0,
        "_": str(int(time.time() * 1000)),
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://data.eastmoney.com/",
    }
    try:
        r = requests.get(_EM_LIST_URL, params=params, headers=headers, timeout=timeout)
        if r.status_code != 200:
            return [], f"http {r.status_code}"
        data = r.json()
        return data.get("data") or [], None
    except Exception as e:
        return [], str(e)


def _normalize_em(raw: dict) -> dict:
    """东方财富原始 item → 我们的字段。"""
    title = raw.get("title", "")
    stock_code = raw.get("stockCode", "") or ""
    stock_name = raw.get("stockName", "") or ""
    publish_date = (raw.get("publishDate") or "")[:10]
    info_code = raw.get("infoCode", "")

    rating = _RATING_NAME.get(raw.get("emRatingCode", ""), raw.get("emRatingName", "") or "—")
    rating_change = _rating_change(
        raw.get("emRatingValue"), raw.get("lastEmRatingValue"), raw.get("ratingChange")
    )

    eps_parts = []
    for label, key in (
        ("今年", "predictThisYearEps"),
        ("明年", "predictNextYearEps"),
        ("后年", "predictNextTwoYearEps"),
    ):
        v = raw.get(key)
        if v:
            eps_parts.append(f"{label}EPS {_fmt_num(v)}")
    eps_forecast = "；".join(eps_parts)

    industry = raw.get("indvInduName") or raw.get("industryName") or ""

    pdf_url = _PDF_URL_TPL.format(info_code=info_code) if info_code else None

    return {
        "info_code": info_code,
        "title": title,
        "stock_code": stock_code,
        "stock_name": stock_name,
        "industry": industry,
        "broker": raw.get("orgSName") or raw.get("orgName") or "",
        "rating": rating,
        "rating_change": rating_change,
        "target_price": "",  # EM list 接口未返回，单篇深度时再补
        "eps_forecast": eps_forecast,
        "publish_date": publish_date,
        "pdf_url": pdf_url,
        "raw": raw,
    }


# ---------- 数据源：AkShare（按股票降级） ----------

def _fetch_akshare_by_stock(symbol: str) -> tuple[list[dict], str | None]:
    """AkShare stock_research_report_em(symbol)，symbol 是 6 位代码。"""
    try:
        import akshare as ak
        df = ak.stock_research_report_em(symbol=symbol)
        if df is None or len(df) == 0:
            return [], None
        items = []
        for _, row in df.head(40).iterrows():
            stock_code = str(row.get("股票代码", "") or "")
            title = str(row.get("报告名称", "") or "")
            publish_date = str(row.get("日期", "") or "")[:10]
            info_url = str(row.get("报告PDF链接", "") or "")
            info_code = ""
            m = re.search(r"H3_([A-Z0-9]+)_", info_url)
            if m:
                info_code = m.group(1)
            eps_parts = []
            for col_label, year in (
                ("2026", "2026"),
                ("2027", "2027"),
                ("2028", "2028"),
            ):
                eps = row.get(f"{col_label}-盈利预测-收益")
                if eps and str(eps) not in ("nan", "None", ""):
                    eps_parts.append(f"{year}EPS {_fmt_num(eps)}")
            items.append({
                "info_code": info_code,
                "title": title,
                "stock_code": stock_code,
                "stock_name": str(row.get("股票简称", "") or ""),
                "industry": str(row.get("行业", "") or ""),
                "broker": str(row.get("机构", "") or ""),
                "rating": str(row.get("东财评级", "") or "—"),
                "rating_change": "维持",
                "target_price": "",
                "eps_forecast": "；".join(eps_parts),
                "publish_date": publish_date,
                "pdf_url": info_url or None,
                "raw": {k: (None if str(v) == "nan" else v) for k, v in row.to_dict().items()},
            })
        return items, None
    except Exception as e:
        return [], str(e)


# ---------- 缓存读写 ----------

def _upsert(conn: sqlite3.Connection, normalized: list[dict]) -> int:
    """写入新研报，返回新增条数（不含已存在）。"""
    new_count = 0
    now = int(time.time())
    for item in normalized:
        key = _dedup_key(item["title"], item["stock_code"], item["publish_date"])
        existing = conn.execute(
            "SELECT 1 FROM reports WHERE dedup_key = ?", (key,)
        ).fetchone()
        if existing:
            continue
        conn.execute(
            """INSERT INTO reports(
                dedup_key, info_code, title, stock_code, stock_name, industry,
                broker, rating, rating_change, target_price, eps_forecast,
                publish_date, pdf_url, raw_json, digest_json, digest_engine,
                fetched_at, digested_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,?,NULL)""",
            (
                key,
                item.get("info_code", ""),
                item["title"],
                item["stock_code"],
                item["stock_name"],
                item["industry"],
                item["broker"],
                item["rating"],
                item["rating_change"],
                item.get("target_price", ""),
                item.get("eps_forecast", ""),
                item["publish_date"],
                item.get("pdf_url"),
                json.dumps(item.get("raw") or {}, ensure_ascii=False, default=str),
                now,
            ),
        )
        new_count += 1
    conn.commit()
    return new_count


def _row_to_dict(row: sqlite3.Row | tuple, cols: list[str]) -> dict:
    return {c: row[i] for i, c in enumerate(cols)}


_REPORT_COLS = [
    "dedup_key", "info_code", "title", "stock_code", "stock_name", "industry",
    "broker", "rating", "rating_change", "target_price", "eps_forecast",
    "publish_date", "pdf_url", "raw_json", "digest_json", "digest_engine",
    "fetched_at", "digested_at",
]


def _query_reports(
    conn: sqlite3.Connection,
    *,
    stock_code: str | None = None,
    industry: str | None = None,
    keyword: str | None = None,
    limit: int = 30,
) -> list[dict]:
    sql = f"SELECT {', '.join(_REPORT_COLS)} FROM reports WHERE 1=1"
    params: list[Any] = []
    if stock_code:
        sql += " AND stock_code = ?"
        params.append(stock_code)
    if industry:
        sql += " AND industry LIKE ?"
        params.append(f"%{industry}%")
    if keyword:
        sql += " AND (title LIKE ? OR stock_name LIKE ?)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    sql += " ORDER BY publish_date DESC, fetched_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(r, _REPORT_COLS) for r in rows]


def _save_digest(conn: sqlite3.Connection, dedup_key: str, digest: dict) -> None:
    conn.execute(
        "UPDATE reports SET digest_json = ?, digest_engine = ?, digested_at = ? WHERE dedup_key = ?",
        (json.dumps(digest, ensure_ascii=False), digest.get("engine", ""), int(time.time()), dedup_key),
    )
    conn.commit()


# ---------- 脱水（批量） ----------

def _ensure_digest(conn: sqlite3.Connection, rows: list[dict], *, max_llm: int = 10, mode: str = "batch") -> None:
    """对没有 digest 的条目跑一次脱水（最多 max_llm 篇）。"""
    pending = [r for r in rows if not r.get("digest_json")]
    if not pending:
        return
    pending = pending[:max_llm]
    try:
        from digest_llm import summarize_batch
    except Exception as e:
        logger.warning(f"digest_llm import failed: {e}")
        return

    payloads = [
        {
            "title": r["title"],
            "broker": r["broker"],
            "rating": r["rating"],
            "rating_change": r["rating_change"],
            "industry": r["industry"],
            "stock_name": r["stock_name"],
            "stock_code": r["stock_code"],
            "target_price": r.get("target_price", ""),
            "eps_forecast": r.get("eps_forecast", ""),
        }
        for r in pending
    ]
    digests = summarize_batch(payloads, mode=mode)
    for r, d in zip(pending, digests):
        _save_digest(conn, r["dedup_key"], d)
        r["digest_json"] = json.dumps(d, ensure_ascii=False)
        r["digest_engine"] = d.get("engine", "")


# ---------- → contract item ----------

def _to_item(r: dict) -> dict:
    digest = {}
    if r.get("digest_json"):
        try:
            digest = json.loads(r["digest_json"])
        except json.JSONDecodeError:
            digest = {}

    stocks = []
    if r.get("stock_code"):
        stocks.append(make_stock_ref(
            code=r["stock_code"], name=r.get("stock_name", ""), market=_to_market(r["stock_code"])
        ))

    tags = []
    if r.get("industry"):
        tags.append(r["industry"])
    if r.get("rating") and r["rating"] not in ("—", ""):
        tags.append(r["rating"])

    publish_date = r.get("publish_date") or ""
    ts = f"{publish_date}T00:00:00" if publish_date else datetime.now().isoformat(timespec="seconds")

    digest_status = "pending"
    engine = r.get("digest_engine") or digest.get("engine") or ""
    if engine == "fallback":
        digest_status = "fallback"
    elif engine == "haiku":
        digest_status = "batch"
    elif engine == "sonnet":
        digest_status = "deep"

    extra = {
        "broker": r.get("broker", ""),
        "rating": r.get("rating", ""),
        "rating_change": r.get("rating_change", ""),
        "target_price": r.get("target_price", ""),
        "eps_forecast": r.get("eps_forecast", ""),
        "core_logic": digest.get("core_logic", ""),
        "catalysts": digest.get("catalysts", []),
        "risks": digest.get("risks", []),
        "summary": digest.get("summary", ""),
        "digest_status": digest_status,
    }

    return make_item(
        id=r["dedup_key"],
        type="research",
        title=r["title"],
        ts=ts,
        stocks=stocks,
        tags=tags,
        href=r.get("pdf_url"),
        extra=extra,
    )


# ---------- 对外 API ----------

def latest(
    *,
    limit: int = 30,
    days: int = 7,
    digest_mode: str = "batch",
    max_llm_per_call: int = 6,
    force_refresh: bool = False,
) -> dict:
    """全市场最新研报（默认 7 天内 30 条）。"""
    conn = _ensure_db()
    last_run = _last_fetch_ts(conn, "latest")
    age = int(time.time()) - last_run
    raw_count = 0
    source = "cache"
    err = None

    if force_refresh or age > _CACHE_TTL_SEC:
        raw_items, err = _fetch_eastmoney(page_size=max(limit * 2, 60), days=days)
        if raw_items:
            normalized = [_normalize_em(x) for x in raw_items]
            raw_count = _upsert(conn, normalized)
            _record_fetch(conn, "latest", raw_count, "eastmoney")
            source = "eastmoney"
        else:
            logger.warning(f"latest fetch eastmoney empty: {err}")

    rows = _query_reports(conn, limit=limit)
    _ensure_digest(conn, rows, max_llm=max_llm_per_call, mode=digest_mode)
    items = [_to_item(r) for r in rows]

    sources = []
    fallback = None
    if source == "eastmoney" or rows:
        sources.append("eastmoney")
    if err and not rows:
        fallback = "akshare"

    qc = simple_qc(items=items, sources=sources or ["cache"], fallback_source=fallback, expected=min(10, limit))
    if err:
        qc["fetch_warning"] = err

    return envelope(
        module="research",
        items=items,
        qc=qc,
        extra_meta={
            "fresh_inserted": raw_count,
            "data_source": source,
            "digest_mode": digest_mode,
        },
    )


def by_stock(code: str, *, limit: int = 20, digest_mode: str = "batch", max_llm_per_call: int = 6) -> dict:
    """按股票代码查研报。code 接受 600519 / 600519.SH / SH600519 多种形态。"""
    if not code:
        return envelope(module="research", items=[], qc=simple_qc(items=[], sources=[]), extra_meta={})

    bare = re.sub(r"[^0-9]", "", code)[:6]
    if not bare:
        return envelope(module="research", items=[], qc=simple_qc(items=[], sources=[]), extra_meta={})

    conn = _ensure_db()
    raw_items, err = _fetch_akshare_by_stock(bare)
    inserted = 0
    if raw_items:
        inserted = _upsert(conn, raw_items)

    rows = _query_reports(conn, stock_code=bare, limit=limit)
    _ensure_digest(conn, rows, max_llm=max_llm_per_call, mode=digest_mode)
    items = [_to_item(r) for r in rows]

    sources = ["akshare"] if raw_items else (["cache"] if rows else [])
    qc = simple_qc(items=items, sources=sources, expected=min(5, limit))
    if err and not rows:
        qc["fetch_warning"] = err

    return envelope(
        module="research",
        items=items,
        qc=qc,
        extra_meta={"stock_code": bare, "fresh_inserted": inserted},
    )


def by_industry(industry: str, *, limit: int = 20, digest_mode: str = "batch") -> dict:
    """按行业过滤已缓存研报。"""
    if not industry:
        return envelope(module="research", items=[], qc=simple_qc(items=[], sources=[]), extra_meta={})
    # 先确保 latest 拉过
    latest(limit=60, max_llm_per_call=0)
    conn = _ensure_db()
    rows = _query_reports(conn, industry=industry, limit=limit)
    _ensure_digest(conn, rows, max_llm=6, mode=digest_mode)
    items = [_to_item(r) for r in rows]
    qc = simple_qc(items=items, sources=["eastmoney"] if items else [], expected=min(5, limit))
    return envelope(module="research", items=items, qc=qc, extra_meta={"industry": industry})


def by_keyword(keyword: str, *, limit: int = 20, digest_mode: str = "batch") -> dict:
    if not keyword:
        return envelope(module="research", items=[], qc=simple_qc(items=[], sources=[]), extra_meta={})
    latest(limit=60, max_llm_per_call=0)
    conn = _ensure_db()
    rows = _query_reports(conn, keyword=keyword, limit=limit)
    _ensure_digest(conn, rows, max_llm=6, mode=digest_mode)
    items = [_to_item(r) for r in rows]
    qc = simple_qc(items=items, sources=["eastmoney"] if items else [], expected=min(5, limit))
    return envelope(module="research", items=items, qc=qc, extra_meta={"keyword": keyword})


def digest_one(report_id: str, *, mode: str = "deep") -> dict:
    """单篇深度脱水。report_id = dedup_key。"""
    conn = _ensure_db()
    rows = conn.execute(
        f"SELECT {', '.join(_REPORT_COLS)} FROM reports WHERE dedup_key = ?",
        (report_id,),
    ).fetchall()
    if not rows:
        return envelope(
            module="research", items=[],
            qc={"status": "failure", "completeness": 0, "sources": [],
                "fallback_source": None, "missing_dimensions": ["report"], "stale_data": [],
                "error": f"report_id 不存在: {report_id}"},
            extra_meta={"report_id": report_id},
        )
    r = _row_to_dict(rows[0], _REPORT_COLS)
    try:
        from digest_llm import summarize_report
        digest = summarize_report({
            "title": r["title"], "broker": r["broker"], "rating": r["rating"],
            "rating_change": r["rating_change"], "industry": r["industry"],
            "stock_name": r["stock_name"], "stock_code": r["stock_code"],
            "target_price": r.get("target_price", ""), "eps_forecast": r.get("eps_forecast", ""),
        }, mode=mode)
        _save_digest(conn, r["dedup_key"], digest)
        r["digest_json"] = json.dumps(digest, ensure_ascii=False)
        r["digest_engine"] = digest.get("engine", "")
    except Exception as e:
        logger.warning(f"digest_one fail: {e}")

    items = [_to_item(r)]
    qc = simple_qc(items=items, sources=["eastmoney"], expected=1)
    return envelope(module="research", items=items, qc=qc, extra_meta={"report_id": report_id, "mode": mode})


# ---------- CLI ----------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="A 股卖方研报脱水")
    parser.add_argument("action", choices=["latest", "by_stock", "by_industry", "by_keyword", "digest_one", "stats"])
    parser.add_argument("--code")
    parser.add_argument("--industry")
    parser.add_argument("--keyword")
    parser.add_argument("--id")
    parser.add_argument("--mode", default="batch")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--max-llm", type=int, default=6)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.action == "latest":
        out = latest(limit=args.limit, days=args.days, digest_mode=args.mode,
                     max_llm_per_call=args.max_llm, force_refresh=args.force)
    elif args.action == "by_stock":
        out = by_stock(args.code or "", limit=args.limit, digest_mode=args.mode, max_llm_per_call=args.max_llm)
    elif args.action == "by_industry":
        out = by_industry(args.industry or "", limit=args.limit, digest_mode=args.mode)
    elif args.action == "by_keyword":
        out = by_keyword(args.keyword or "", limit=args.limit, digest_mode=args.mode)
    elif args.action == "digest_one":
        out = digest_one(args.id or "", mode=args.mode)
    else:
        conn = _ensure_db()
        total = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        digested = conn.execute("SELECT COUNT(*) FROM reports WHERE digest_json IS NOT NULL").fetchone()[0]
        last_run = _last_fetch_ts(conn, "latest")
        out = {
            "total": total, "digested": digested,
            "last_fetch_ts": last_run,
            "last_fetch_ago_sec": int(time.time()) - last_run if last_run else None,
            "db_path": str(_DB_PATH),
        }

    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))

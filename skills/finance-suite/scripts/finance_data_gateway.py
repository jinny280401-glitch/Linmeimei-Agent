"""Finance Data Gateway v0.

Small wrapper around existing Finance Suite data calls. It borrows OpenBB's
"connect once, consume everywhere" idea, but does not introduce a new plugin
system or refactor existing tools.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from finance_data_contract import build_response


PROVIDER_CHAIN = ["wind", "tushare", "joinquant", "akshare", "cache"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _bare_symbol(symbol: str) -> str:
    return symbol.strip().split(".")[0]


def _normalize_symbol(symbol: str | None) -> str | None:
    if not symbol:
        return symbol
    symbol = symbol.strip().upper()
    if "." in symbol:
        return symbol
    if symbol.startswith(("6", "9")):
        return f"{symbol}.SH"
    if symbol.startswith(("0", "3")):
        return f"{symbol}.SZ"
    return symbol


def _has_data(data: Any) -> bool:
    return bool(data) if data is not None else False


def _try_wind(symbol: str) -> dict[str, Any] | None:
    import wind_data

    data = wind_data.get_stock_snapshot(symbol)
    return data or None


def _try_tushare(symbol: str) -> dict[str, Any] | None:
    import tushare_data

    data = tushare_data.get_stock_snapshot(symbol)
    return data or None


def _try_joinquant(symbol: str) -> dict[str, Any] | None:
    import joinquant_data

    data = joinquant_data.get_stock_snapshot(symbol)
    return data or None


def _try_akshare(symbol: str) -> dict[str, Any] | None:
    import akshare as ak
    import stock_data

    df = stock_data._with_timeout(ak.stock_zh_a_spot_em, timeout_seconds=8.0)
    if df is None or len(df) == 0:
        return None
    bare = _bare_symbol(symbol)
    row = df[df["代码"].astype(str) == bare]
    if row.empty:
        return None
    item = row.iloc[0]
    return {
        "code": str(item.get("代码", bare)),
        "name": str(item.get("名称", "")),
        "price": item.get("最新价"),
        "change": item.get("涨跌幅"),
        "pe": item.get("市盈率-动态"),
        "pb": item.get("市净率"),
        "mv": item.get("总市值"),
        "volume": item.get("成交量"),
        "amount": item.get("成交额"),
    }


def _try_cache(symbol: str) -> dict[str, Any] | None:
    import stock_data

    bare = _bare_symbol(symbol)
    data = stock_data._fetch_realtime_from_cache(bare)
    return data or None


def _freshness_for(provider: str, data: dict[str, Any]) -> str:
    if provider == "cache":
        try:
            import stock_data

            return "stale" if stock_data._is_realtime_stale() else "cached"
        except Exception:
            return "cached"
    if provider == "joinquant" or data.get("used_fallback_date"):
        return "delayed"
    if provider == "tushare":
        return "daily"
    return "realtime"


def _as_of_for(provider: str, data: dict[str, Any]) -> str:
    for key in ("trade_date", "data_date", "date", "datetime", "time"):
        value = data.get(key)
        if value:
            return str(value)
    return _utc_now_iso()


def _quote(symbol: str) -> dict[str, Any]:
    normalized_symbol = _normalize_symbol(symbol)
    attempted_sources: list[dict[str, str]] = []
    runners: dict[str, Callable[[str], dict[str, Any] | None]] = {
        "wind": _try_wind,
        "tushare": _try_tushare,
        "joinquant": _try_joinquant,
        "akshare": _try_akshare,
        "cache": _try_cache,
    }

    for provider in PROVIDER_CHAIN:
        try:
            data = runners[provider](normalized_symbol or symbol)
            if _has_data(data):
                freshness = _freshness_for(provider, data)
                qc = {
                    "status": "success",
                    "completeness": 1.0,
                    "sources": [provider],
                    "fallback_source": None if provider == "wind" else provider,
                    "missing_dimensions": [],
                    "stale_data": [data.get("_metadata")] if freshness in {"delayed", "stale"} and data.get("_metadata") else [],
                    "attempted_sources": attempted_sources + [{"provider": provider, "status": "success"}],
                    "provider_chain": PROVIDER_CHAIN,
                }
                return build_response(
                    ok=True,
                    symbol=normalized_symbol,
                    data_type="quote",
                    provider=provider,
                    freshness=freshness,
                    as_of=_as_of_for(provider, data),
                    data=data,
                    qc=qc,
                )
            attempted_sources.append({"provider": provider, "status": "empty"})
        except Exception as exc:
            attempted_sources.append({"provider": provider, "status": "error", "error": str(exc)})

    return build_response(
        ok=False,
        symbol=normalized_symbol,
        data_type="quote",
        provider=None,
        freshness="unavailable",
        data={},
        qc={
            "status": "failure",
            "completeness": 0,
            "sources": [],
            "fallback_source": "cache",
            "missing_dimensions": ["quote"],
            "stale_data": [],
            "attempted_sources": attempted_sources,
            "provider_chain": PROVIDER_CHAIN,
            "error": "quote 多源查询失败（Wind/Tushare/JoinQuant/AkShare/cache）",
        },
    )


def get_finance_data(data_type: str, symbol: str | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return Finance Suite data through the unified v0 contract."""
    del params
    normalized_type = (data_type or "").strip().lower()
    if normalized_type != "quote":
        return build_response(
            ok=False,
            symbol=_normalize_symbol(symbol),
            data_type=normalized_type,
            provider=None,
            freshness="unsupported",
            data={},
            qc={
                "status": "failure",
                "completeness": 0,
                "sources": [],
                "fallback_source": None,
                "missing_dimensions": [normalized_type or "data_type"],
                "stale_data": [],
                "error": 'Finance Data Gateway v0 only supports data_type="quote".',
            },
        )
    if not symbol:
        return build_response(
            ok=False,
            symbol=None,
            data_type="quote",
            provider=None,
            freshness="invalid_request",
            data={},
            qc={
                "status": "failure",
                "completeness": 0,
                "sources": [],
                "fallback_source": None,
                "missing_dimensions": ["symbol"],
                "stale_data": [],
                "error": "symbol is required for quote.",
            },
        )
    return _quote(symbol)

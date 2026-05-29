"""
JoinQuant（聚宽）数据获取模块
数据源优先级链第三层：Wind → Tushare → JoinQuant → AkShare

核心优势：
- 历史估值分位（PE/PB 近10年百分位）
- 基本面快照（PE/PB/市值/ROE）
- 基本面因子选股（trading-system 不可用时的降级）

环境变量：JQ_USERNAME / JQ_PASSWORD
用法: python3 joinquant_data.py --test
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)

_JQ_USERNAME = os.getenv("JQ_USERNAME", "")
_JQ_PASSWORD = os.getenv("JQ_PASSWORD", "")
_jq_available: Optional[bool] = None


def _ensure_jq() -> bool:
    """懒加载初始化 JoinQuant，失败静默降级"""
    global _jq_available
    if _jq_available is True:
        return True
    if not _JQ_USERNAME or not _JQ_PASSWORD:
        _jq_available = False
        logger.warning("JoinQuant 未配置：缺少 JQ_USERNAME / JQ_PASSWORD 环境变量")
        return False
    try:
        import jqdatasdk as jq
        jq.auth(_JQ_USERNAME, _JQ_PASSWORD)
        _jq_available = True
        logger.info("JoinQuant 已初始化")
        return True
    except Exception as e:
        _jq_available = False
        logger.warning(f"JoinQuant 初始化失败：{e}")
        return False


def _to_jq_code(code: str) -> str:
    """转换股票代码：600519.SH → 600519.XSHG，000858.SZ → 000858.XSHE"""
    bare = code.split(".")[0]
    if bare.startswith(("6", "9")):
        return f"{bare}.XSHG"
    return f"{bare}.XSHE"


def _from_jq_code(jq_code: str) -> str:
    """反向转换：600519.XSHG → 600519.SH"""
    bare = jq_code.split(".")[0]
    suffix = "SH" if jq_code.endswith("XSHG") else "SZ"
    return f"{bare}.{suffix}"


def check_connection() -> dict:
    """检查 JoinQuant 连接状态"""
    status = check_joinquant_health()
    return {"connected": status.get("connected", False), "source": "joinquant" if status.get("connected") else "unavailable", **status}


def _metadata(data_date: str | None = None, used_fallback_date: bool = False) -> dict:
    return {
        "source": "joinquant",
        "data_date": data_date,
        "used_fallback_date": used_fallback_date,
        "account_type": "trial",
        "limitations": ["前15个月~前3个月", "实时数据不可用或受限"],
    }


def _with_metadata(data: dict, data_date: str | None = None, used_fallback_date: bool = False) -> dict:
    meta = _metadata(data_date, used_fallback_date)
    data.update(meta)
    data["_metadata"] = meta
    return data


def _stale_entry(data_date: str | None) -> dict:
    return {
        "source": "joinquant",
        "reason": "trial_account_delay",
        "data_date": data_date,
        "message": "JoinQuant trial account returned delayed historical data.",
    }


def check_joinquant_health() -> dict:
    """检查 JoinQuant 认证与样例查询状态，供 MCP/API 健康检查使用。"""
    status = {
        "connected": False,
        "auth_ok": False,
        "sample_query_ok": False,
        "source": "joinquant",
        "account_type": "trial",
        "latest_available_date": None,
        "sample_data_date": None,
        "used_fallback_date": False,
        "limitations": ["前15个月~前3个月", "实时数据不可用或受限"],
    }
    if not _ensure_jq():
        status["error"] = "JoinQuant unavailable or credentials missing"
        return status
    status["connected"] = True
    status["auth_ok"] = True
    try:
        import jqdatasdk as jq

        jq_code = _to_jq_code("600519.SH")
        df, actual_date, used_fallback = _get_fundamentals_with_fallback(
            jq,
            jq.query(jq.valuation.code, jq.valuation.pe_ratio).filter(jq.valuation.code == jq_code),
        )
        status.update({
            "sample_query_ok": df is not None and not df.empty,
            "latest_available_date": actual_date,
            "sample_data_date": actual_date,
            "used_fallback_date": used_fallback,
        })
    except Exception as e:
        status["error"] = str(e)
    return status


check_status = check_joinquant_health


def _latest_date() -> str:
    """返回最近可用的交易日期（试用账号数据截止前3个月，正式账号用今天）"""
    today = datetime.today()
    # 先尝试今天，若无数据则退到3个月前（试用账号限制）
    return today.strftime("%Y-%m-%d")


def _fallback_date() -> str:
    """试用账号兜底日期：3个月前"""
    return (datetime.today() - timedelta(days=95)).strftime("%Y-%m-%d")


def _get_fundamentals_with_fallback(jq, query_obj, preferred_date: str | None = None) -> tuple[Any | None, str | None, bool]:
    """先查今天，若空则退到3个月前（兼容试用账号）"""
    fallback = _fallback_date()
    dates = []
    for date in [preferred_date, _latest_date(), fallback]:
        if date and date not in dates:
            dates.append(date)
    for date in dates:
        try:
            df = jq.get_fundamentals(query_obj, date=date)
            if df is not None and not df.empty:
                return df, date, date == fallback and preferred_date != fallback
        except Exception:
            continue
    return None, None, False


def get_stock_snapshot(code: str) -> dict:
    """
    个股基本面快照（PE/PB/市值/ROE）
    返回格式与 wind_data.get_stock_snapshot() 兼容
    """
    if not _ensure_jq():
        return {}
    try:
        import jqdatasdk as jq
        jq_code = _to_jq_code(code)
        df, actual_date, used_fallback = _get_fundamentals_with_fallback(
            jq,
            jq.query(jq.valuation, jq.indicator).filter(jq.valuation.code == jq_code),
        )
        if df is None or df.empty:
            return _with_metadata({}, actual_date, used_fallback)
        row = df.iloc[0]
        return _with_metadata({
            "code": code,
            "pe": _safe_float(row.get("pe_ratio")),
            "pb": _safe_float(row.get("pb_ratio")),
            "market_cap": _safe_float(row.get("market_cap")),  # 亿元
            "roe": _safe_float(row.get("roe")),
        }, actual_date, used_fallback)
    except Exception as e:
        logger.warning(f"JoinQuant get_stock_snapshot 失败 {code}: {e}")
        return {}


def get_valuation_history(code: str) -> dict:
    """
    历史估值分位（PE/PB 近10年百分位）
    返回格式与 wind_data.get_valuation_history() 兼容
    """
    if not _ensure_jq():
        return {}
    try:
        import jqdatasdk as jq
        import pandas as pd

        jq_code = _to_jq_code(code)
        end = datetime.today()
        start = end - timedelta(days=3650)

        # 按季度采样，最多40个数据点
        date_range = pd.date_range(start, end, freq="QE")
        dates = [d.strftime("%Y-%m-%d") for d in date_range][-40:]

        records = []
        actual_dates = []
        for d in dates:
            try:
                df = jq.get_fundamentals(
                    jq.query(jq.valuation).filter(jq.valuation.code == jq_code),
                    date=d,
                )
                if df is not None and not df.empty:
                    pe = _safe_float(df["pe_ratio"].iloc[0])
                    pb = _safe_float(df["pb_ratio"].iloc[0])
                    if pe and pe > 0:
                        records.append({"date": d, "pe": pe, "pb": pb})
                        actual_dates.append(d)
            except Exception:
                continue

        if not records:
            return _with_metadata({}, None, False)

        pe_series = [r["pe"] for r in records if r.get("pe")]
        pb_series = [r["pb"] for r in records if r.get("pb")]
        current_pe = pe_series[-1] if pe_series else None
        current_pb = pb_series[-1] if pb_series else None

        def percentile(series: list, val) -> Optional[float]:
            if not series or val is None:
                return None
            return round(sum(1 for x in series if x <= val) / len(series) * 100, 1)

        actual_date = actual_dates[-1] if actual_dates else None
        return _with_metadata({
            "code": code,
            "pe_current": current_pe,
            "pb_current": current_pb,
            "pe_percentile_10y": percentile(pe_series, current_pe),
            "pb_percentile_10y": percentile(pb_series, current_pb),
            "pe_min": min(pe_series) if pe_series else None,
            "pe_max": max(pe_series) if pe_series else None,
            "pb_min": min(pb_series) if pb_series else None,
            "pb_max": max(pb_series) if pb_series else None,
            "history_quarters": len(records),
            "history": records,
        }, actual_date, False)
    except Exception as e:
        logger.warning(f"JoinQuant get_valuation_history 失败 {code}: {e}")
        return {}


def get_factor_signals(scan_date: str = None) -> dict:
    """
    基本面因子选股（trading-system 不可用时的降级方案）
    筛选：PE 10-30、ROE > 15%、市值 50-500亿，按 ROE 降序取前20
    返回格式与 factor_scan.get_factor_signals() 兼容
    """
    if not _ensure_jq():
        return {"error": "JoinQuant 不可用"}
    try:
        import jqdatasdk as jq

        preferred_date = scan_date or _latest_date()
        query_obj = jq.query(
            jq.valuation.code,
            jq.valuation.pe_ratio,
            jq.valuation.pb_ratio,
            jq.valuation.market_cap,
            jq.indicator.roe,
        ).filter(
            jq.valuation.pe_ratio > 10,
            jq.valuation.pe_ratio < 30,
            jq.indicator.roe > 15,
            jq.valuation.market_cap > 50,
            jq.valuation.market_cap < 500,
        ).order_by(
            jq.indicator.roe.desc()
        ).limit(20)
        df, date, used_fallback = _get_fundamentals_with_fallback(
            jq,
            query_obj,
            preferred_date=preferred_date,
        )

        if df is None or df.empty:
            result = {
                "scan_date": date or preferred_date, "signals": [],
                "stats": {"hits": 0}, "_source": "joinquant",
            }
            return _with_metadata(result, date, used_fallback)

        # 批量获取股票名称
        codes = df["code"].tolist()
        name_map = _get_name_map(jq, codes)

        signals = []
        for _, row in df.iterrows():
            jq_code = row["code"]
            std_code = _from_jq_code(jq_code)
            signals.append({
                "code": std_code,
                "name": name_map.get(jq_code, jq_code.split(".")[0]),
                "pe": round(_safe_float(row.get("pe_ratio")) or 0, 1),
                "pb": round(_safe_float(row.get("pb_ratio")) or 0, 1),
                "roe": round(_safe_float(row.get("roe")) or 0, 1),
                "market_cap": round(_safe_float(row.get("market_cap")) or 0, 1),
                "composite_score": round(_safe_float(row.get("roe")) or 0, 1),
            })

        result = {
            "scan_date": date,
            "signals": signals,
            "stats": {
                "hits": len(signals),
                "total_stocks": "全市场",
                "after_coarse": len(signals),
            },
            "factors_used": ["pe_range_10_30", "roe_gt_15", "market_cap_50_500亿"],
            "market_env": {
                "status": "JoinQuant 基本面筛选（非技术因子）",
                "safe": True,
            },
            "_source": "joinquant",
        }
        return _with_metadata(result, date, used_fallback)
    except Exception as e:
        logger.warning(f"JoinQuant get_factor_signals 失败: {e}")
        return {"error": str(e)}


def get_financials(code: str) -> dict:
    """轻量财务指标兜底，供 MCP financials action 使用。"""
    if not _ensure_jq():
        return {}
    try:
        import jqdatasdk as jq

        jq_code = _to_jq_code(code)
        df, actual_date, used_fallback = _get_fundamentals_with_fallback(
            jq,
            jq.query(jq.valuation, jq.indicator, jq.income).filter(jq.valuation.code == jq_code),
        )
        if df is None or df.empty:
            return _with_metadata({}, actual_date, used_fallback)
        row = df.iloc[0]
        return _with_metadata({
            "code": code,
            "financials": [{
                "date": actual_date,
                "roe": _safe_float(row.get("roe")),
                "roa": _safe_float(row.get("roa")),
                "gross_profit_margin": _safe_float(row.get("gross_profit_margin")),
                "net_profit_margin": _safe_float(row.get("net_profit_margin")),
                "operating_revenue": _safe_float(row.get("operating_revenue")),
                "net_profit": _safe_float(row.get("net_profit")),
            }],
        }, actual_date, used_fallback)
    except Exception as e:
        logger.warning(f"JoinQuant get_financials 失败 {code}: {e}")
        return {"error": str(e)}


# ---- 内部工具 ----

def _safe_float(val) -> Optional[float]:
    """安全转 float，None/NaN/0 返回 None"""
    try:
        v = float(val)
        return v if v == v and v != 0 else None  # NaN check
    except (TypeError, ValueError):
        return None


def _get_name_map(jq, codes: list) -> dict:
    """批量获取股票名称，失败返回空字典"""
    result = {}
    for code in codes:
        try:
            info = jq.get_security_info(code)
            if info:
                result[code] = info.display_name
        except Exception:
            continue
    return result


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="JoinQuant 数据模块测试")
    parser.add_argument("--test", action="store_true", help="连接测试 + 快照")
    parser.add_argument("--code", type=str, default="600519.SH", help="股票代码")
    parser.add_argument("--action", type=str, default="snapshot",
                        choices=["snapshot", "valuation", "factors"])
    args = parser.parse_args()

    if args.test or args.action == "snapshot":
        print("=== 连接测试 ===")
        print(json.dumps(check_connection(), ensure_ascii=False, indent=2))
        print(f"\n=== 个股快照 {args.code} ===")
        print(json.dumps(get_stock_snapshot(args.code), ensure_ascii=False, indent=2))

    elif args.action == "valuation":
        print(f"=== 历史估值分位 {args.code} ===")
        result = get_valuation_history(args.code)
        summary = {k: v for k, v in result.items() if k != "history"}
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    elif args.action == "factors":
        print("=== 因子选股信号 ===")
        print(json.dumps(get_factor_signals(), ensure_ascii=False, indent=2, default=str))

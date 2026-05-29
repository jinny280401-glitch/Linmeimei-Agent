"""
MCP Server 全量回归 + 日志汇总脚本

测试覆盖：
  connect / stock / financials / valuation / consensus / factor_scan
  每个动作捕获 _qc.status / sources / fallback_source / completeness
  支持模拟 trading-system 不可用，验证 JoinQuant 降级是否生效

运行：
  export JQ_USERNAME=xxx JQ_PASSWORD=xxx
  .venv/bin/python3.12 scripts/mcp_tools_log_summary.py

输出：
  mcp_tools_log_summary.json  （每条记录含 tool/args/status/sources/fallback/data_sample）
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import joinquant_data

# ── 测试参数 ──────────────────────────────────────────────────────────────────
TEST_STOCKS = ["600519.SH", "000001.SZ", "601318.SH", "000333.SZ", "300750.SZ"]
TEST_DATES  = ["2026-05-05", ""]   # "" = 默认今天
SUMMARY_FILE = ROOT / "mcp_tools_log_summary.json"

# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _parse(raw: str) -> tuple[dict, str]:
    """解析 _wrap_response 格式：'<json>\n\n<body>'"""
    if not raw:
        return {}, ""
    parts = raw.split("\n\n", 1)
    try:
        envelope = json.loads(parts[0])
    except Exception:
        envelope = {}
    body = parts[1] if len(parts) > 1 else ""
    return envelope, body


def _extract_body_json(body: str) -> dict:
    """尽量从正文里提取结构化 JSON，兼容前面带人类可读摘要的返回。"""
    if not body:
        return {}
    candidates = [body]
    json_start = body.find("{")
    if json_start >= 0:
        candidates.append(body[json_start:])
    last_json_start = body.rfind("\n{")
    if last_json_start >= 0:
        candidates.insert(0, body[last_json_start + 1:])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            continue
    return {}


def _record(tool: str, args: dict, raw: str) -> dict:
    """把一次工具调用结果标准化为汇总记录"""
    envelope, body = _parse(raw)
    qc = envelope.get("_qc", {})
    body_json = _extract_body_json(body)
    source_used = (
        qc.get("source_used")
        or body_json.get("source_used")
        or body_json.get("source")
        or ((qc.get("sources") or [None])[-1] if len(qc.get("sources") or []) == 1 else None)
    )
    return {
        "timestamp":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tool":           tool,
        "args":           args,
        "status":         qc.get("status", "unknown"),
        "completeness":   qc.get("completeness"),
        "sources":        qc.get("sources", []),
        "source_used":    source_used,
        "fallback_source":qc.get("fallback_source"),
        "fallback_triggered": qc.get("fallback_triggered", bool(qc.get("fallback_source"))),
        "missing":        qc.get("missing_dimensions", []),
        "stale":          qc.get("stale_data", []),
        "error":          qc.get("error"),
        "data_sample":    body[:400] if body else "",
    }


def _run(tool: str, args: dict, fn, *a, **kw) -> dict:
    try:
        raw = fn(*a, **kw)
        return _record(tool, args, raw)
    except Exception as e:
        return {"tool": tool, "args": args, "status": "exception", "error": str(e)}


def _print_row(rec: dict):
    status_icon = {"success": "✅", "partial": "⚠️", "failure": "❌"}.get(rec["status"], "❓")
    src = ", ".join(rec.get("sources") or []) or "—"
    fb  = rec.get("fallback_source") or "—"
    miss = ", ".join(rec.get("missing") or []) or "—"
    print(f"  {status_icon} {rec['tool']:<22} src={src:<12} fallback={fb:<12} "
          f"completeness={rec.get('completeness', '?'):<5} missing=[{miss}]")
    if rec.get("error"):
        print(f"     ⚠ error: {rec['error']}")


def _latest_joinquant_usage() -> dict:
    if not SUMMARY_FILE.exists():
        return {}
    try:
        payload = json.loads(SUMMARY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    records = payload.get("records", [])
    for rec in reversed(records):
        if rec.get("tool") == "connect":
            continue
        sources = rec.get("sources") or []
        if rec.get("source_used") == "joinquant" or "joinquant" in sources or rec.get("fallback_source") == "joinquant":
            rec = dict(rec)
            rec["_summary_timestamp"] = payload.get("timestamp")
            return rec
    return {}


def run_joinquant_health_check() -> None:
    status = joinquant_data.check_joinquant_health()
    recent = _latest_joinquant_usage()

    print("JoinQuant Health Check")
    print("----------------------")
    print(f"connected: {status.get('connected')}")
    print(f"auth_ok: {status.get('auth_ok')}")
    print(f"sample_query_ok: {status.get('sample_query_ok')}")
    print(f"account_type: {status.get('account_type')}")
    print(f"latest_available_date: {status.get('latest_available_date') or status.get('sample_data_date')}")
    limitations = status.get("limitations") or []
    if limitations:
        print(f"limitations: {', '.join(limitations)}")
    if status.get("error"):
        print(f"error: {status.get('error')}")

    print("")
    print("Recent Usage")
    print("------------")
    if recent:
        stale = recent.get("stale") or []
        summary_ts = recent.get("_summary_timestamp")
        record_ts = recent.get("timestamp")
        print(f"summary_timestamp: {summary_ts or 'unknown'}")
        print(f"last_success_at: {record_ts or summary_ts or 'unknown'}")
        print(f"tool: {recent.get('tool')}")
        print(f"source_used: {recent.get('source_used') or ', '.join(recent.get('sources') or []) or 'unknown'}")
        print(f"sources: {', '.join(recent.get('sources') or []) or 'unknown'}")
        print(f"fallback_source: {recent.get('fallback_source')}")
        print(f"fallback_triggered: {recent.get('fallback_triggered', bool(recent.get('fallback_source')))}")
        print(f"data_date: {(stale[0] or {}).get('data_date') if stale else status.get('latest_available_date')}")
        print(f"stale_marked: {bool(stale)}")
        if not record_ts:
            print("recent_usage_note: legacy summary record without per-call timestamp; rerun full summary to refresh")
        if (recent.get("source_used") == "joinquant" or recent.get("sources") == ["joinquant"]) and recent.get("fallback_source") not in (None, "joinquant"):
            print("recent_usage_warning: legacy summary likely contains old fallback_source mapping; current factor_scan uses fallback_source=joinquant")
    else:
        print("last_success_at: unavailable")
        print("tool: direct_health_check")
        print("source_used: joinquant")
        print("fallback_source: none")
        print("fallback_triggered: false")
        print(f"data_date: {status.get('latest_available_date') or status.get('sample_data_date')}")
        print(f"stale_marked: {status.get('used_fallback_date', False)}")


# ── 测试用例 ──────────────────────────────────────────────────────────────────

def run_connect(summary: list):
    import mcp_server

    print("\n[1] connect — 数据源连接状态")
    rec = _run("connect", {}, mcp_server.wind_query, action="connect")
    _print_row(rec)
    summary.append(rec)


def run_stock_snapshot(summary: list):
    import mcp_server

    print("\n[2] stock — 个股快照（Wind → Tushare → JoinQuant）")
    for stock in TEST_STOCKS:
        rec = _run("stock", {"code": stock}, mcp_server.wind_query, action="stock", code=stock)
        _print_row(rec)
        summary.append(rec)


def run_financials(summary: list):
    import mcp_server

    print("\n[3] financials — 财报（Tushare → JoinQuant → AkShare）")
    for stock in TEST_STOCKS:
        rec = _run("financials", {"code": stock}, mcp_server.wind_query, action="financials", code=stock)
        _print_row(rec)
        summary.append(rec)


def run_valuation(summary: list):
    import mcp_server

    print("\n[4] valuation — 估值历史（Wind → JoinQuant → Tushare → AkShare）")
    for stock in TEST_STOCKS:
        rec = _run("valuation", {"code": stock}, mcp_server.wind_query, action="valuation", code=stock)
        _print_row(rec)
        summary.append(rec)


def run_consensus(summary: list):
    import mcp_server

    print("\n[5] consensus — 卖方一致预期（Wind → Tushare）")
    for stock in TEST_STOCKS[:3]:
        rec = _run("consensus", {"code": stock}, mcp_server.wind_query, action="consensus", code=stock)
        _print_row(rec)
        summary.append(rec)


def run_factor_scan_normal(summary: list):
    import mcp_server

    print("\n[6] factor_scan — 正常模式（trading-system）")
    for date in TEST_DATES:
        rec = _run("factor_scan", {"date": date or "today"}, mcp_server.factor_scan, date=date)
        _print_row(rec)
        summary.append(rec)


def run_factor_scan_fallback(summary: list):
    """monkeypatch trading-system → 强制触发 JoinQuant 降级"""
    import mcp_server
    import factor_scan as _fs_module

    print("\n[7] factor_scan — 降级模式（模拟 trading-system 不可用）")
    original = _fs_module.get_factor_signals

    def _fake(_date=None):
        return {"error": "simulated trading-system unavailable"}

    _fs_module.get_factor_signals = _fake
    try:
        for date in TEST_DATES:
            rec = _run(
                "factor_scan[fallback]",
                {"date": date or "today", "simulated_failure": True},
                mcp_server.factor_scan,
                date=date,
            )
            _print_row(rec)
            summary.append(rec)
    finally:
        _fs_module.get_factor_signals = original


def run_stock_analysis(summary: list):
    import mcp_server

    print("\n[8] stock_analysis — 全维度个股（AkShare + Wind）")
    import asyncio
    for stock in TEST_STOCKS[:3]:
        try:
            raw = asyncio.run(mcp_server.stock_analysis(stock))
            rec = _record("stock_analysis", {"query": stock}, raw)
        except Exception as e:
            rec = {"tool": "stock_analysis", "args": {"query": stock}, "status": "exception", "error": str(e)}
        _print_row(rec)
        summary.append(rec)


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MCP Server 全量回归 + 日志汇总")
    parser.add_argument("--check-joinquant", action="store_true", help="只执行 JoinQuant 健康检查")
    args = parser.parse_args()

    if args.check_joinquant:
        run_joinquant_health_check()
        return

    if not os.environ.get("JQ_USERNAME") or not os.environ.get("JQ_PASSWORD"):
        print("请先设置环境变量：JQ_USERNAME / JQ_PASSWORD")
        sys.exit(1)

    print("=" * 70)
    print("MCP Server 全量回归 + 日志汇总")
    print(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    summary: list[dict] = []

    run_connect(summary)
    run_stock_snapshot(summary)
    run_financials(summary)
    run_valuation(summary)
    run_consensus(summary)
    run_factor_scan_normal(summary)
    run_factor_scan_fallback(summary)
    run_stock_analysis(summary)

    # ── 汇总统计 ──────────────────────────────────────────────────────────────
    total   = len(summary)
    success = sum(1 for r in summary if r["status"] == "success")
    partial = sum(1 for r in summary if r["status"] == "partial")
    failure = sum(1 for r in summary if r["status"] in ("failure", "exception"))

    print("\n" + "=" * 70)
    print(f"汇总：共 {total} 次调用  ✅ {success} 成功  ⚠️ {partial} 部分  ❌ {failure} 失败")

    # 数据源分布
    from collections import Counter
    src_counter = Counter(
        src for r in summary for src in (r.get("sources") or [])
    )
    print("数据源分布：", dict(src_counter))

    # 降级触发次数
    fallback_count = sum(1 for r in summary if r.get("fallback_source"))
    print(f"降级触发次数：{fallback_count}")

    # ── 写 JSON ───────────────────────────────────────────────────────────────
    output = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stats": {
            "total": total, "success": success,
            "partial": partial, "failure": failure,
            "source_distribution": dict(src_counter),
            "fallback_triggered": fallback_count,
        },
        "records": summary,
    }
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存：{SUMMARY_FILE}")


if __name__ == "__main__":
    main()

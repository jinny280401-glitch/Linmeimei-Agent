#!/usr/bin/env python3
"""
Finance Suite MCP Server — 本地验证脚本（方案 A：直接 import）

直接调用 MCP 工具函数，验证多源降级、_qc 字段完整性。
生成 Markdown 测试报告到 logs/。

用法：
    cd /Users/Zhuanz/finance-suite
    python3 scripts/test_mcp_local.py
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

os.chdir(REPO_ROOT)

from mcp_server import (
    stock_analysis,
    macro_snapshot,
    market_pulse,
    factor_scan,
    wind_query,
)

REPORT_DIR = REPO_ROOT / "logs"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TEST_CASES = [
    {"name": "stock_analysis", "fn": stock_analysis, "args": ("贵州茅台",), "is_async": True, "timeout": 60},
    {"name": "macro_snapshot", "fn": macro_snapshot, "args": (), "is_async": True, "timeout": 30},
    {"name": "market_pulse", "fn": market_pulse, "args": (), "is_async": True, "timeout": 30},
    {"name": "factor_scan", "fn": factor_scan, "args": (), "is_async": False, "timeout": 30},
    {"name": "wind_query(connect)", "fn": wind_query, "args": ("connect",), "is_async": False, "timeout": 60},
    {"name": "wind_query(valuation)", "fn": wind_query, "args": ("valuation", "600519.SH"), "is_async": False, "timeout": 30},
]


class CaseTimeout(Exception):
    pass


def _alarm_handler(signum, frame):
    raise CaseTimeout()


def parse_envelope(raw: str) -> dict:
    """MCP 工具返回 'JSON\\n\\n正文' 格式，解析首段 JSON 拿 _qc"""
    if not isinstance(raw, str) or not raw.strip():
        return {"_qc": {"status": "failure", "error": "empty"}}
    head = raw.split("\n\n", 1)[0]
    try:
        return json.loads(head)
    except json.JSONDecodeError:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"_qc": {"status": "failure", "error": "non-JSON response"}}


def run_case(case: dict) -> dict:
    start = time.perf_counter()
    record = {
        "tool": case["name"],
        "status": None,
        "completeness": None,
        "sources": [],
        "fallback_source": None,
        "missing_dimensions": [],
        "latency_ms": 0.0,
        "error": None,
    }
    timeout = case.get("timeout", 30)
    prev_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.alarm(timeout)
    try:
        if case["is_async"]:
            raw = asyncio.run(case["fn"](*case["args"]))
        else:
            raw = case["fn"](*case["args"])
        envelope = parse_envelope(raw)
        qc = envelope.get("_qc", {})
        record["status"] = qc.get("status")
        record["completeness"] = qc.get("completeness")
        record["sources"] = qc.get("sources") or []
        record["fallback_source"] = qc.get("fallback_source")
        record["missing_dimensions"] = qc.get("missing_dimensions") or []
        if qc.get("error"):
            record["error"] = qc["error"]
    except CaseTimeout:
        record["error"] = f"timeout after {timeout}s"
        record["status"] = "failure"
    except Exception as exc:
        record["error"] = f"{exc.__class__.__name__}: {str(exc)[:200]}"
        record["status"] = "failure"
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev_handler)
    record["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
    return record


def summarize(records: list[dict]) -> dict:
    total = len(records)
    success = sum(1 for r in records if r["status"] == "success")
    partial = sum(1 for r in records if r["status"] == "partial")
    failure = sum(1 for r in records if r["status"] == "failure")
    fallback_used = sum(1 for r in records if r["fallback_source"])
    return {
        "total": total,
        "success": success,
        "partial": partial,
        "failure": failure,
        "success_rate": round(success / total, 2) if total else 0,
        "fallback_used": fallback_used,
    }


def render_markdown(records: list[dict], summary: dict, ts: str) -> str:
    lines = [
        f"# MCP Server 本地验证报告",
        "",
        f"**Timestamp:** {ts}",
        f"**Total:** {summary['total']} / **Success:** {summary['success']} / "
        f"**Partial:** {summary['partial']} / **Failure:** {summary['failure']} / "
        f"**Fallback used:** {summary['fallback_used']}",
        "",
        "| Tool | Status | Completeness | Sources | Fallback | Latency(ms) | Error |",
        "|------|--------|--------------|---------|----------|-------------|-------|",
    ]
    for r in records:
        sources = ", ".join(r["sources"]) if r["sources"] else "-"
        fb = r["fallback_source"] or "-"
        err = (r["error"] or "-").replace("|", "\\|")
        lines.append(
            f"| {r['tool']} | {r['status']} | {r['completeness']} | {sources} "
            f"| {fb} | {r['latency_ms']} | {err} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    print("=== Finance Suite MCP 本地验证 ===")
    records = [run_case(case) for case in TEST_CASES]
    for r in records:
        print(
            f"{r['tool']:30s} status={r['status']} "
            f"sources={r['sources']} fallback={r['fallback_source']} "
            f"latency={r['latency_ms']}ms"
        )

    summary = summarize(records)
    print(
        f"\nSummary: {summary['success']}/{summary['total']} success "
        f"({summary['success_rate']*100:.0f}%), "
        f"fallback used {summary['fallback_used']} times"
    )

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = REPORT_DIR / f"mcp_local_test_{ts}.md"
    report_path.write_text(render_markdown(records, summary, ts), encoding="utf-8")
    print(f"\nReport saved: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

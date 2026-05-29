#!/usr/bin/env python3
"""
Finance Suite MCP Server local enhanced validation.

Features:
1. Test local HTTP tool endpoints.
2. Track per-tool success, source/fallback, status, completeness, latency.
3. Generate Markdown and/or HTML reports under logs/.
4. Keep frontend and production routes untouched.

Usage:
    python3 scripts/test_mcp_local_enhanced.py
    python3 scripts/test_mcp_local_enhanced.py --base-url http://localhost:8765/api/tool --format both
"""

from __future__ import annotations

import argparse
import html
import json
import os
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL.*")

import requests


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "http://localhost:8765/api/tool"
DEFAULT_REPORT_DIR = ROOT / "logs"

TEST_CASES: list[dict[str, Any]] = [
    {"tool": "stock_snapshot", "params": {"code": "600519.SH"}},
    {"tool": "financials", "params": {"code": "600519.SH", "report_type": "annual"}},
    {"tool": "valuation_history", "params": {"code": "600519.SH"}},
    {"tool": "quant_factor", "params": {"code": "600519.SH", "factor_name": "pe_ratio"}},
    {"tool": "wind_raw", "params": {"query": "close(600519.SH, '2026-05-15')"}},
    {"tool": "check_sources", "params": {}},
]


def extract_qc(payload: dict[str, Any]) -> dict[str, Any]:
    qc = payload.get("qc") or payload.get("_qc") or {}
    return qc if isinstance(qc, dict) else {}


def extract_source(payload: dict[str, Any], qc: dict[str, Any]) -> str | None:
    sources = qc.get("sources")
    if qc.get("source"):
        return str(qc["source"])
    if qc.get("source_used"):
        return str(qc["source_used"])
    if isinstance(sources, list) and len(sources) == 1:
        return str(sources[0])
    data = payload.get("data")
    if isinstance(data, dict):
        source = data.get("source") or data.get("source_used")
        return str(source) if source else None
    return None


def sample_payload(payload: dict[str, Any], limit: int = 300) -> str:
    data = payload.get("data", {})
    try:
        return json.dumps(data or {}, ensure_ascii=False, default=str)[:limit]
    except TypeError:
        return str(data)[:limit]


def test_mcp_tool(base_url: str, tool_name: str, params: dict[str, Any], timeout: float) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/{tool_name}"
    started = time.perf_counter()
    result: dict[str, Any] = {
        "tool": tool_name,
        "success": False,
        "source": None,
        "fallback_source": None,
        "status": None,
        "completeness": None,
        "latency_ms": None,
        "data_sample": None,
        "error": None,
    }

    try:
        response = requests.get(url, params=params, timeout=timeout)
        result["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
        response.raise_for_status()
        payload = response.json()
        qc = extract_qc(payload)
        status = qc.get("status")
        result.update(
            {
                "success": status == "success",
                "source": extract_source(payload, qc),
                "fallback_source": qc.get("fallback_source"),
                "status": status,
                "completeness": qc.get("completeness"),
                "data_sample": sample_payload(payload),
            }
        )
    except requests.exceptions.RequestException as exc:
        result["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
        result["error"] = str(exc)
    except json.JSONDecodeError:
        result["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
        result["error"] = "Non-JSON response"
    except Exception as exc:
        result["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
        result["error"] = f"{exc.__class__.__name__}: {exc}"

    return result


def build_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    success = sum(1 for item in results if item["success"])
    failed = total - success
    sources: dict[str, int] = {}
    fallback_sources: dict[str, int] = {}

    for item in results:
        source = item.get("source") or "unknown"
        sources[source] = sources.get(source, 0) + 1
        fallback = item.get("fallback_source")
        if fallback:
            fallback_sources[str(fallback)] = fallback_sources.get(str(fallback), 0) + 1

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "success_rate": round(success / total, 4) if total else 0,
        "source_distribution": sources,
        "fallback_distribution": fallback_sources,
    }


def generate_markdown(report: dict[str, Any], path: Path) -> None:
    rows = [
        "# MCP Server Local Test Report",
        f"**Timestamp:** {report['timestamp']}",
        "",
        "## Summary",
        "",
        f"- Total: {report['summary']['total']}",
        f"- Success: {report['summary']['success']}",
        f"- Failed: {report['summary']['failed']}",
        f"- Success rate: {report['summary']['success_rate']:.2%}",
        f"- Source distribution: `{json.dumps(report['summary']['source_distribution'], ensure_ascii=False)}`",
        f"- Fallback distribution: `{json.dumps(report['summary']['fallback_distribution'], ensure_ascii=False)}`",
        "",
        "## Results",
        "",
        "| Tool | Success | Source | Fallback | Status | Completeness | Latency ms | Data Sample | Error |",
        "|------|---------|--------|----------|--------|--------------|------------|-------------|-------|",
    ]
    for item in report["results"]:
        rows.append(
            "| {tool} | {success} | {source} | {fallback} | {status} | {completeness} | {latency} | {sample} | {error} |".format(
                tool=markdown_cell(item.get("tool")),
                success=markdown_cell(item.get("success")),
                source=markdown_cell(item.get("source")),
                fallback=markdown_cell(item.get("fallback_source")),
                status=markdown_cell(item.get("status")),
                completeness=markdown_cell(item.get("completeness")),
                latency=markdown_cell(item.get("latency_ms")),
                sample=markdown_cell(item.get("data_sample")),
                error=markdown_cell(item.get("error")),
            )
        )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")[:500]


def generate_html(report: dict[str, Any], path: Path) -> None:
    summary = report["summary"]
    rows = []
    for item in report["results"]:
        rows.append(
            "<tr>"
            f"<td>{escape(item.get('tool'))}</td>"
            f"<td>{escape(item.get('success'))}</td>"
            f"<td>{escape(item.get('source'))}</td>"
            f"<td>{escape(item.get('fallback_source'))}</td>"
            f"<td>{escape(item.get('status'))}</td>"
            f"<td>{escape(item.get('completeness'))}</td>"
            f"<td>{escape(item.get('latency_ms'))}</td>"
            f"<td><pre>{escape(item.get('data_sample'))}</pre></td>"
            f"<td>{escape(item.get('error'))}</td>"
            "</tr>"
        )

    body = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>MCP Server Local Test Report</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #17202a; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    th, td {{ border: 1px solid #d7dde5; padding: 8px; vertical-align: top; }}
    th {{ background: #f2f5f8; text-align: left; }}
    pre {{ white-space: pre-wrap; margin: 0; max-width: 420px; }}
  </style>
</head>
<body>
  <h1>MCP Server Local Test Report</h1>
  <p><strong>Timestamp:</strong> {escape(report['timestamp'])}</p>
  <h2>Summary</h2>
  <ul>
    <li>Total: {summary['total']}</li>
    <li>Success: {summary['success']}</li>
    <li>Failed: {summary['failed']}</li>
    <li>Success rate: {summary['success_rate']:.2%}</li>
    <li>Source distribution: {escape(json.dumps(summary['source_distribution'], ensure_ascii=False))}</li>
    <li>Fallback distribution: {escape(json.dumps(summary['fallback_distribution'], ensure_ascii=False))}</li>
  </ul>
  <h2>Results</h2>
  <table>
    <thead>
      <tr><th>Tool</th><th>Success</th><th>Source</th><th>Fallback</th><th>Status</th><th>Completeness</th><th>Latency ms</th><th>Data Sample</th><th>Error</th></tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</body>
</html>
"""
    path.write_text(body, encoding="utf-8")


def escape(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def write_reports(report: dict[str, Any], report_dir: Path, fmt: str) -> list[Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = report["timestamp"].replace(":", "").replace("-", "").replace(".", "")
    paths: list[Path] = []

    if fmt in ("markdown", "both"):
        path = report_dir / f"mcp_local_test_{timestamp}.md"
        generate_markdown(report, path)
        paths.append(path)

    if fmt in ("html", "both"):
        path = report_dir / f"mcp_local_test_{timestamp}.html"
        generate_html(report, path)
        paths.append(path)

    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finance Suite MCP local enhanced validation.")
    parser.add_argument("--base-url", default=os.getenv("MCP_LOCAL_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--format", choices=["markdown", "html", "both"], default="both")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results: list[dict[str, Any]] = []

    for case in TEST_CASES:
        result = test_mcp_tool(args.base_url, case["tool"], case["params"], args.timeout)
        results.append(result)
        print(
            "{tool}: success={success}, source={source}, fallback={fallback}, status={status}, latency_ms={latency}, error={error}".format(
                tool=result["tool"],
                success=result["success"],
                source=result["source"],
                fallback=result["fallback_source"],
                status=result["status"],
                latency=result["latency_ms"],
                error=result["error"],
            )
        )

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "summary": build_summary(results),
        "results": results,
    }
    paths = write_reports(report, Path(args.report_dir), args.format)

    for path in paths:
        print(f"Report saved: {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Production smoke check for Finance Suite.

This is intentionally conservative: it verifies that the current production site
is reachable and that unauthenticated API calls fail safely instead of returning
5xx. It does not require credentials and does not mutate server state.

Run:
  cd /Users/Zhuanz/finance-suite
  .venv/bin/python3.12 scripts/site_smoke_check.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


BASE = "https://www.touziagent.com"
TIMEOUT = 15


@dataclass(frozen=True)
class Check:
    name: str
    method: str
    path: str
    expected: set[int]
    critical: bool = True
    body: bytes | None = None
    content_type: str | None = None
    validator: str | None = None


CHECKS = [
    Check("index page", "GET", "/app/index.html", {200}),
    Check("stock page", "GET", "/app/stock.html", {200}),
    Check("deep research page", "GET", "/app/deep-research.html", {200}),
    Check("auction page", "GET", "/app/auction.html", {200}),
    Check(
        "api analyze unauth guard",
        "POST",
        "/api/analyze",
        {401},
        body=json.dumps({"skill_type": "stock", "query": "贵州茅台", "extra_content": ""}).encode("utf-8"),
        content_type="application/json",
    ),
    # Not production-critical yet. If this returns 200, it must still be the
    # known compatibility stub until a deployment window connects live research_digest.
    Check(
        "optional intel research route",
        "GET",
        "/api/intel/research?limit=1",
        {200, 404},
        critical=False,
        validator="intel_research_stub",
    ),
]


def request_status(check: Check) -> tuple[int | None, str]:
    url = BASE + check.path
    req = urllib.request.Request(url, data=check.body, method=check.method)
    if check.content_type:
        req.add_header("Content-Type", check.content_type)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read(2000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(200).decode("utf-8", errors="replace")
    except Exception as e:
        return None, str(e)


def validate_body(check: Check, status: int | None, body: str) -> tuple[bool, str]:
    if check.validator != "intel_research_stub" or status == 404:
        return True, ""
    try:
        data = json.loads(body or "{}")
    except json.JSONDecodeError as e:
        return False, f"expected JSON body for intel research route: {e}"
    qc = data.get("_qc") if isinstance(data, dict) else None
    if not isinstance(qc, dict):
        return False, "missing _qc object in intel research response"
    if qc.get("status") != "failure":
        return False, f"expected _qc.status=failure stub, got {qc.get('status')!r}"
    error = str(qc.get("error") or "")
    if "not connected to a live upstream" not in error:
        return False, f"unexpected intel research stub error: {error[:120]}"
    return True, ""


def main() -> int:
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"Finance Suite production smoke check @ {started}")
    failures = []
    warnings = []
    for check in CHECKS:
        status, detail = request_status(check)
        body_ok, body_issue = validate_body(check, status, detail)
        ok = status in check.expected and body_ok
        label = "OK" if ok else ("WARN" if not check.critical else "FAIL")
        print(f"[{label}] {check.name}: status={status} expected={sorted(check.expected)}")
        if body_issue:
            print(f"      detail={body_issue}")
        elif detail and not ok:
            print(f"      detail={detail[:180]}")
        if not ok and check.critical:
            failures.append(check.name)
        elif not ok:
            warnings.append(check.name)

    if failures:
        print("\nCritical failures:")
        for name in failures:
            print(f"- {name}")
        return 1
    if warnings:
        print("\nWarnings:")
        for name in warnings:
            print(f"- {name}")
    print("\nSmoke check passed for critical production paths.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

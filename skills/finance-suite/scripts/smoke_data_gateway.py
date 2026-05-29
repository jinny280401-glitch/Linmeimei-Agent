"""Smoke test for Finance Data Gateway v0.

Run after starting the local demo API:
  .venv/bin/uvicorn scripts.research_demo_api:app --host 127.0.0.1 --port 8765
"""
from __future__ import annotations

import json
import os
import sys
from urllib.parse import urlencode
from urllib.request import urlopen


REQUIRED_FIELDS = {"ok", "provider", "freshness", "as_of", "data", "qc"}


def main() -> int:
    base_url = os.getenv("FINANCE_DATA_GATEWAY_URL", "http://127.0.0.1:8765")
    query = urlencode({"data_type": "quote", "symbol": "600519.SH"})
    url = f"{base_url.rstrip('/')}/api/data/query?{query}"

    with urlopen(url, timeout=45) as response:
        status = response.status
        payload = json.loads(response.read().decode("utf-8"))

    missing = sorted(REQUIRED_FIELDS - set(payload))
    ok = status == 200 and not missing
    print(json.dumps({"ok": ok, "status": status, "missing": missing, "payload": payload}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

"""Smoke test for Research Editorial Layer v0."""
from __future__ import annotations

import json
import os
import sys
from urllib.parse import urlencode
from urllib.request import urlopen


REQUIRED_FIELDS = {"title", "report_date", "data_sources"}
REQUIRED_SECTION_IDS = {f"{i:02d}" for i in range(11)}
FORBIDDEN_TERMS = {
    "buy",
    "sell",
    "hold",
    "score",
    "target_price",
    "看多",
    "看空",
    "买入",
    "卖出",
    "推荐",
}


def main() -> int:
    base_url = os.getenv("RESEARCH_HERO_URL", "http://127.0.0.1:8765")
    query = urlencode({"symbol": "300750.SZ"})
    url = f"{base_url.rstrip('/')}/api/research/hero?{query}"

    with urlopen(url, timeout=20) as response:
        status = response.status
        payload = json.loads(response.read().decode("utf-8"))

    field_missing = sorted(REQUIRED_FIELDS - set(payload))
    sections = payload.get("research_map", {}).get("sections", [])
    section_ids = {str(item.get("section_id", "")) for item in sections}
    section_missing = sorted(REQUIRED_SECTION_IDS - section_ids)
    text = json.dumps(payload, ensure_ascii=False).lower()
    forbidden_hits = sorted(term for term in FORBIDDEN_TERMS if term.lower() in text)
    ok = status == 200 and not field_missing and not section_missing and not forbidden_hits

    print(json.dumps({
        "ok": ok,
        "status": status,
        "field_missing": field_missing,
        "section_missing": section_missing,
        "forbidden_hits": forbidden_hits,
        "payload": payload,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

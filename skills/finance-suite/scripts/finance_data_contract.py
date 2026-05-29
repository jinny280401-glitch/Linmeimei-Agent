"""Minimal Finance Suite data contract.

This module is intentionally small: it gives REST, MCP, frontend, and agents a
single JSON shape without changing the existing business tools underneath.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_response(
    *,
    ok: bool,
    symbol: str | None,
    data_type: str,
    provider: str | None,
    freshness: str,
    as_of: str | None = None,
    data: Any = None,
    qc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the unified Finance Data Gateway response."""
    normalized_qc = dict(qc or {})
    normalized_qc.setdefault("status", "success" if ok else "failure")
    normalized_qc.setdefault("sources", [provider] if provider else [])
    normalized_qc.setdefault("missing_dimensions", [] if ok else [data_type])
    normalized_qc.setdefault("stale_data", [])

    return {
        "ok": bool(ok),
        "symbol": symbol,
        "data_type": data_type,
        "provider": provider,
        "freshness": freshness,
        "as_of": as_of or _utc_now_iso(),
        "data": data if data is not None else {},
        "qc": normalized_qc,
    }

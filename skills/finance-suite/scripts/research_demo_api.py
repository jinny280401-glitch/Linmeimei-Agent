"""
8765 research demo sandbox.

仅用于：
- 脱水研报 UI
- intel/research demo
- 前端联调

不提供：
- /api/analyze 真实分析
- 登录鉴权
- 生产级 router
- Finance Suite 全站能力

真实功能请使用：
https://www.touziagent.com

Purpose:
- Bypass the production finance-suite-web repo for research feedback loops.
- Serve app/index.html and expose /api/intel/research directly.
- Let agents verify "one real research card in the browser" before deployment wiring.

Run:
  cd /Users/Zhuanz/finance-suite
  OPENROUTER_API_KEY=... .venv/bin/uvicorn scripts.research_demo_api:app --host 127.0.0.1 --port 8765

Without an LLM key, research_digest still returns real Eastmoney reports with rule fallback.
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Body, FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
APP_DIR = ROOT / "app"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

load_dotenv(ROOT / ".env")

app = FastAPI(title="Finance Suite Research Demo")
app.mount("/app", StaticFiles(directory=APP_DIR, html=True), name="app")


@app.get("/")
def index():
    return RedirectResponse("/app/index.html")


@app.get("/api/intel/research")
def research(
    limit: int = Query(6, ge=1, le=30),
    max_llm: int = Query(2, ge=0, le=10),
    mode: str = Query("batch", pattern="^(batch|deep)$"),
    force: bool = Query(False),
):
    import research_digest

    try:
        return research_digest.latest(
            limit=limit,
            digest_mode=mode,
            max_llm_per_call=max_llm,
            force_refresh=force,
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "items": [],
                "_qc": {
                    "status": "failure",
                    "completeness": 0,
                    "sources": [],
                    "fallback_source": None,
                    "missing_dimensions": ["research"],
                    "stale_data": [],
                    "error": str(e),
                },
                "meta": {"module": "research", "count": 0},
            },
        )


@app.get("/api/intel/market-context")
def market_context_layer():
    import market_context

    try:
        return market_context.snapshot_sync()
    except Exception as e:
        return JSONResponse(
            status_code=200,
            content={
                "title": "今日市场画像",
                "positioning": "市场结构摘要 / Market Context Layer",
                "generated_at": "",
                "date_label": "",
                "conclusion": "数据不足，暂不下结论",
                "metrics": {},
                "context": {
                    "market_preference": "数据不足，暂不下结论",
                    "theme_concentration": "数据不足，暂不下结论",
                    "breadth": "数据不足，暂不下结论",
                    "top_sector": None,
                },
                "themes": [],
                "roles": {
                    "streak_samples": [],
                    "large_turnover_samples": [],
                    "high_change_samples": [],
                },
                "monitoring": ["数据不足，暂不下结论"],
                "disclaimer": "本页面呈现市场结构数据，不含操作建议。仅供参考，不构成投资建议。",
                "_qc": {
                    "status": "failure",
                    "completeness": 0,
                    "sources": [],
                    "fallback_source": None,
                    "missing_dimensions": ["market_context"],
                    "stale_data": [],
                    "error": str(e),
                },
            },
        )


@app.get("/api/data/query")
def data_query(
    data_type: str = Query(..., min_length=1),
    symbol: str | None = Query(None),
):
    import finance_data_gateway

    return finance_data_gateway.get_finance_data(data_type=data_type, symbol=symbol)


@app.get("/api/research/hero")
def research_hero(symbol: str = Query(..., min_length=1)):
    import research_editorial_blocks

    return research_editorial_blocks.demo_hero_for_symbol(symbol)


@app.get("/api/intel/discussions")
def discussions():
    return {"items": [], "_qc": {"status": "failure", "sources": [], "completeness": 0}, "meta": {"count": 0}}


@app.get("/api/intel/hot-stocks")
def hot_stocks():
    return {"items": [], "_qc": {"status": "failure", "sources": [], "completeness": 0}, "meta": {"count": 0}}


@app.get("/api/intel/golden-pit")
def golden_pit_demo(realtime: bool = Query(False)):
    return {
        "hits": [],
        "watchlist": [],
        "market_env": {"status": "demo"},
        "scan_date": "local-demo",
        "source_used": "demo",
        "fallback_chain": [],
        "fallback_triggered": False,
        "_qc": {
            "status": "partial",
            "completeness": 0.2,
            "sources": ["local_demo"],
            "fallback_source": None,
            "missing_dimensions": ["production_golden_pit_scan"],
            "stale_data": [],
            "note": "本地 research demo 不运行完整黄金坑扫描；生产站使用 /api/intel/golden-pit。",
        },
    }


@app.post("/api/analyze")
def analyze_demo(payload: dict = Body(default_factory=dict)):
    skill_type = payload.get("skill_type", "")
    query = payload.get("query", "")
    if skill_type != "auction":
        return JSONResponse(
            status_code=404,
            content={"detail": f"本地 demo 仅提供 auction stub，不提供 {skill_type or 'unknown'} 分析。"},
        )

    return {
        "_qc": {
            "status": "partial",
            "completeness": 0.1,
            "sources": ["local_demo"],
            "fallback_source": None,
            "missing_dimensions": ["production_api_analyze"],
            "stale_data": [],
            "note": "本地 8765 是 research demo，不运行完整集合竞价分析；生产站使用 finance-suite-web /api/analyze。",
        },
        "skill_type": "auction",
        "query": query,
        "data": {
            "demo": True,
            "message": "这是本地 demo JSON stub。要跑真实集合竞价，请打开 https://www.touziagent.com/app/auction.html。",
        },
    }


@app.get("/api/watchlist/list")
def watchlist():
    return {"_qc": {"status": "failure", "sources": []}, "data": []}


@app.get("/favicon.ico")
def favicon():
    path = APP_DIR / "favicon.ico"
    if path.exists():
        return FileResponse(path)
    return JSONResponse({})

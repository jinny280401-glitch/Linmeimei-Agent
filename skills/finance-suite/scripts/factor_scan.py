"""
因子选股信号 — 调用 trading-system 扫描引擎
数据源：BaoStock历史日线 + AkShare全市场快照

独立CLI脚本，无内部依赖
用法: python3 factor_scan.py [--date 2025-04-03]
"""
from __future__ import annotations

import subprocess
import json
import sys
import os
from datetime import datetime

# trading-system 路径（同一台机器）
TRADING_SYSTEM_PATH = "/Users/Zhuanz/trading-system"
FACTOR_SCAN_SCRIPT = f"{TRADING_SYSTEM_PATH}/scripts/factor_scan.py"
FALLBACK_CHAIN = ["trading_system", "joinquant", "wind", "tushare", "akshare"]


def _trial_stale_entry(data_date: str | None) -> dict:
    return {
        "source": "joinquant",
        "reason": "trial_account_delay",
        "data_date": data_date,
        "message": "JoinQuant trial account returned delayed historical data.",
    }


def _build_qc(data: dict, source_used: str, fallback_triggered: bool, attempted_sources: list[str]) -> dict:
    hits = data.get("hits") or []
    signals = data.get("signals") or []
    market_env = data.get("market_env") or {}
    has_hits = bool(hits or signals)
    has_market_env = bool(market_env)

    if has_hits:
        status = "success"
        completeness = 1.0
        missing_dimensions = []
    elif has_market_env:
        status = "partial"
        completeness = 0.5
        missing_dimensions = ["候选信号"]
    else:
        status = "partial"
        completeness = 0.3
        missing_dimensions = ["候选信号", "市场环境"]

    stale_data = []
    meta = data.get("_metadata") if isinstance(data.get("_metadata"), dict) else data
    if source_used == "joinquant" and meta.get("used_fallback_date"):
        stale_data.append(_trial_stale_entry(meta.get("data_date") or data.get("scan_date")))

    return {
        "status": status,
        "completeness": completeness,
        "sources": attempted_sources,
        "fallback_source": source_used if fallback_triggered else None,
        "missing_dimensions": missing_dimensions,
        "stale_data": stale_data,
    }


def _finalize(data: dict, source_used: str, fallback_triggered: bool, attempted_sources: list[str]) -> dict:
    data.setdefault("scan_date", datetime.now().strftime("%Y-%m-%d"))
    data["source_used"] = source_used
    data["fallback_chain"] = FALLBACK_CHAIN
    data["fallback_triggered"] = fallback_triggered
    if "_qc" not in data:
        data["_qc"] = _build_qc(data, source_used, fallback_triggered, attempted_sources)
    return data


def _joinquant_fallback(scan_date: str = None, attempted_sources: list[str] | None = None) -> dict:
    attempted_sources = attempted_sources or ["trading_system", "joinquant"]
    try:
        import joinquant_data

        data = joinquant_data.get_factor_signals(scan_date)
        if data and "error" not in data and "signals" in data:
            return _finalize(data, "joinquant", True, attempted_sources)
        fallback_data = {
            "scan_date": scan_date or datetime.now().strftime("%Y-%m-%d"),
            "signals": [],
            "market_env": {},
            "error": data.get("error", "JoinQuant returned no factor signals") if isinstance(data, dict) else "JoinQuant returned no data",
        }
        return _finalize(fallback_data, "joinquant", True, attempted_sources)
    except Exception as e:
        return _finalize({
            "scan_date": scan_date or datetime.now().strftime("%Y-%m-%d"),
            "signals": [],
            "market_env": {},
            "error": str(e),
        }, "joinquant", True, attempted_sources)


def get_factor_signals(scan_date: str = None) -> dict:
    """调用 trading-system 因子扫描，返回结构化数据"""
    if os.getenv("FORCE_TRADING_SYSTEM_FAIL") == "1":
        return _joinquant_fallback(scan_date)

    cmd = ["python3", FACTOR_SCAN_SCRIPT, "--json"]
    if scan_date:
        cmd.append(scan_date)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
            cwd=TRADING_SYSTEM_PATH,
        )
        if result.returncode == 0:
            # 过滤掉 stderr 中的进度信息，只解析 stdout 的 JSON
            stdout = result.stdout.strip()
            # JSON 从第一个 { 开始
            json_start = stdout.find("{")
            if json_start >= 0:
                data = json.loads(stdout[json_start:])
                if isinstance(data, dict) and "error" not in data:
                    return _finalize(data, "trading_system", False, ["trading_system"])
        return _joinquant_fallback(scan_date)
    except subprocess.TimeoutExpired:
        return _joinquant_fallback(scan_date)
    except FileNotFoundError:
        return _joinquant_fallback(scan_date)
    except Exception as e:
        return _joinquant_fallback(scan_date)


def format_factor_signals(data: dict) -> str:
    """格式化为LLM可读文本，嵌入集合竞价Prompt"""
    if "error" in data:
        return f"【因子选股信号】数据暂不可用: {data['error']}"

    parts = []
    parts.append("=== 因子选股信号（量化扫描）===")
    parts.append(f"扫描日期：{data.get('scan_date', '未知')}")
    parts.append(f"扫描耗时：{data.get('elapsed_seconds', '?')}秒")
    parts.append("")

    # 市场环境
    env = data.get("market_env", {})
    parts.append(f"【市场环境】{env.get('status', '未知')}")
    if "index_close" in env:
        parts.append(f"  沪深300: {env['index_close']:.2f}  MA20: {env['ma20']:.2f}  偏离: {env['diff_pct']:.1f}%")
    safe = env.get("safe", True)
    if not safe:
        parts.append("  !! 大盘在20日均线下方，建议谨慎操作 !!")
    parts.append("")

    # 扫描统计
    stats = data.get("stats", {})
    parts.append(f"【扫描统计】全市场{stats.get('total_stocks', '?')}只 → "
                 f"粗筛{stats.get('after_coarse', '?')}只 → "
                 f"命中{stats.get('hits', 0)}只")
    parts.append("")

    # 选股因子说明
    factor_desc = {
        "limit_up_gene": "涨停基因（半年内有涨停记录=有爆发力）",
        "below_limit_up_price": "跌破涨停价（当前价<最近涨停价=洗盘充分）",
        "consolidation": "横盘筑底（60日振幅<15%+缩量=底部扎实）",
        "bbiboll": "BBIBOLL低轨反弹（触及布林下轨后反弹=入场时机）",
        "consecutive_decline": "连跌缩量（连续下跌+缩量=卖压衰竭）",
    }
    parts.append("【选股逻辑】同时满足以下条件:")
    for f in data.get("factors_used", []):
        parts.append(f"  - {factor_desc.get(f, f)}")
    parts.append("")

    # 命中股票
    signals = data.get("signals", [])
    if not signals:
        parts.append("【命中股票】今日无命中")
    else:
        parts.append(f"【命中股票】共{len(signals)}只（按综合评分排序）")
        for i, sig in enumerate(signals, 1):
            score_details = []
            for k, v in sig.items():
                if k.endswith("_score") and k != "composite_score":
                    label = k.replace("_score", "")
                    score_details.append(f"{label}:{v}")
            detail_str = " | ".join(score_details) if score_details else ""
            parts.append(
                f"  {i}. {sig.get('name', '')}({sig['code']}) "
                f"收盘{sig['close']} 涨跌{sig['pct_chg']}% "
                f"综合评分:{sig.get('composite_score', 0)} "
                f"[{detail_str}]"
            )

    parts.append("")
    parts.append("注：因子信号为量化筛选结果，需结合盘面环境综合判断。")
    return "\n".join(parts)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="获取因子选股信号")
    parser.add_argument("--date", type=str, default=None, help="扫描日期 YYYY-MM-DD")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")
    args = parser.parse_args()

    print("正在执行因子扫描（可能需要1-3分钟）...", flush=True)

    data = get_factor_signals(args.date)

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    else:
        print(format_factor_signals(data))

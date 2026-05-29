import os
import sys
import json
from pathlib import Path

# 让脚本可直接 import 项目根目录下的 mcp_server.py
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mcp_server  # noqa: E402
import factor_scan as fs  # noqa: E402

TEST_STOCKS = ["600519.SH", "000001.SZ", "601318.SH", "000333.SZ", "300750.SZ"]


def parse_wrapped_response(text: str) -> tuple[dict, str]:
    """mcp_server._wrap_response 格式: '<json>\n\n<content>'"""
    if not text:
        return {}, ""
    parts = text.split("\n\n", 1)
    qc_envelope = {}
    body = ""
    try:
        qc_envelope = json.loads(parts[0])
    except Exception:
        pass
    if len(parts) > 1:
        body = parts[1]
    return qc_envelope, body


def pretty_qc(title: str, qc: dict):
    print(f"\n=== {title} ===")
    print(json.dumps(qc, indent=2, ensure_ascii=False))


def test_factor_scan_fallback():
    """
    模拟 trading-system 不可用：
    - 临时 monkeypatch factor_scan.get_factor_signals 返回 error
    - 调用 mcp_server.factor_scan
    - 观察 _qc.sources 是否降级到 joinquant/wind/tushare/akshare
    """
    original = fs.get_factor_signals

    def fake_get_factor_signals(_date=None):
        return {"error": "simulated trading-system unavailable"}

    fs.get_factor_signals = fake_get_factor_signals
    try:
        raw = mcp_server.factor_scan("")
        env, body = parse_wrapped_response(raw)
        qc = env.get("_qc", {})
        pretty_qc("factor_scan fallback test", qc)
        print("Sample Body:")
        print(body[:600] if body else "<empty>")
    finally:
        fs.get_factor_signals = original


def test_wind_query_batch():
    """
    批量测试多只股票的多源降级表现。
    重点看 _qc.sources / _qc.fallback_source。
    """
    for stock in TEST_STOCKS:
        for action in ("stock", "valuation", "financials"):
            raw = mcp_server.wind_query(action=action, code=stock, max_peers=5)
            env, body = parse_wrapped_response(raw)
            qc = env.get("_qc", {})
            print(f"\n--- {stock} | action={action} ---")
            print("QC:", json.dumps(qc, indent=2, ensure_ascii=False))
            print("Body sample:")
            print((body[:300] + "...") if len(body) > 300 else (body or "<empty>"))


def main():
    print("开始测试：交易系统不可用时的降级链 + 批量股票多源返回")
    test_factor_scan_fallback()
    test_wind_query_batch()


if __name__ == "__main__":
    if not os.environ.get("JQ_USERNAME") or not os.environ.get("JQ_PASSWORD"):
        print("请先设置环境变量：JQ_USERNAME / JQ_PASSWORD")
        sys.exit(1)

    main()

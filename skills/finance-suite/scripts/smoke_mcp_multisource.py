import asyncio
import json
from mcp_server import stock_analysis, wind_query, factor_scan

async def run_smoke_tests():
    results = {}

    # ----------------------
    # 1️⃣ 数据源健康检查
    # ----------------------
    try:
        connect_status = wind_query(action="connect")
        results["wind_connect"] = connect_status
    except Exception as e:
        results["wind_connect"] = {"error": str(e)}

    # ----------------------
    # 2️⃣ 股票快照
    # ----------------------
    try:
        stock_snap = wind_query(action="stock", code="600519.SH")
        results["stock_snapshot"] = stock_snap
    except Exception as e:
        results["stock_snapshot"] = {"error": str(e)}

    # ----------------------
    # 3️⃣ 估值历史
    # ----------------------
    try:
        valuation_hist = wind_query(action="valuation", code="600519.SH")
        results["valuation_history"] = valuation_hist
    except Exception as e:
        results["valuation_history"] = {"error": str(e)}

    # ----------------------
    # 4️⃣ 个股全维度分析
    # ----------------------
    try:
        analysis = await stock_analysis("贵州茅台")
        results["stock_analysis"] = analysis
    except Exception as e:
        results["stock_analysis"] = {"error": str(e)}

    # ----------------------
    # 5️⃣ 量化因子扫描
    # ----------------------
    try:
        factor_res = factor_scan()  # 同步
        results["factor_scan"] = factor_res
    except Exception as e:
        results["factor_scan"] = {"error": str(e)}

    # ----------------------
    # 输出 JSON
    # ----------------------
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(run_smoke_tests())

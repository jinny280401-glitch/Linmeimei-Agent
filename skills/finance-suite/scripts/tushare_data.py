"""
Tushare Pro 数据获取模块
提供财报、一致预期、行业数据等高级金融数据
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Tushare Pro Token
_TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "ac6471c66535d4aa49516341175ae6d7a7ba763682fad2b4559a05b3")
_tushare_available = None
_pro = None


def _ensure_tushare():
    """懒加载初始化 Tushare Pro"""
    global _tushare_available, _pro

    if _tushare_available is True:
        return True

    try:
        import tushare as ts
        ts.set_token(_TUSHARE_TOKEN)
        _pro = ts.pro_api()
        _tushare_available = True
        logger.info("✅ Tushare Pro 已初始化")
        return True
    except Exception as e:
        _tushare_available = False
        logger.warning(f"⚠️ Tushare 初始化失败：{e}")
        return False


def _convert_code(code: str) -> str:
    """转换股票代码格式：600519.SH -> 600519.SH (Tushare 格式)"""
    if "." in code:
        return code
    # 如果没有后缀，尝试添加
    if code.startswith("6"):
        return f"{code}.SH"
    elif code.startswith(("0", "3")):
        return f"{code}.SZ"
    return code


# ---- 核心接口 ----

def check_connection() -> dict:
    """检查 Tushare 连接状态"""
    ok = _ensure_tushare()
    return {"connected": ok, "source": "tushare" if ok else "unavailable"}


def get_stock_snapshot(code: str) -> dict:
    """
    获取股票快照数据（实时行情）
    返回：收盘价、涨跌幅、成交量、成交额
    """
    if not _ensure_tushare():
        return {}

    try:
        ts_code = _convert_code(code)
        # 获取最近一天的数据
        df = _pro.daily(
            ts_code=ts_code,
            start_date=(datetime.now() - timedelta(days=5)).strftime("%Y%m%d"),
            end_date=datetime.now().strftime("%Y%m%d")
        )

        if len(df) > 0:
            row = df.iloc[-1]  # 最新一天
            return {
                "code": code,
                "close": float(row['close']),
                "change": float(row['pct_chg']),
                "volume": float(row['vol']) * 100,  # 手 -> 股
                "amount": float(row['amount']) * 1000,  # 千元 -> 元
                "trade_date": row['trade_date']
            }
    except Exception as e:
        logger.error(f"❌ Tushare 获取股票快照失败：{e}")

    return {}


def get_financials(code: str, report_type: str = "income") -> list:
    """
    获取财报数据
    report_type: "income"（利润表）/ "balance"（资产负债表）/ "cashflow"（现金流）
    返回：最近4期财报数据
    """
    if not _ensure_tushare():
        return []

    try:
        ts_code = _convert_code(code)

        if report_type == "income":
            # 利润表
            df = _pro.income(ts_code=ts_code, limit=4)
            if len(df) > 0:
                result = []
                for _, row in df.iterrows():
                    result.append({
                        "report_date": row.get('end_date', ''),
                        "ann_date": row.get('ann_date', ''),
                        "revenue": float(row.get('total_revenue', 0)) / 10000,  # 元 -> 万元
                        "net_profit": float(row.get('n_income', 0)) / 10000,
                        "eps": float(row.get('basic_eps', 0)),
                        "roe": float(row.get('roe', 0)),
                        "gross_margin": float(row.get('grossprofit_margin', 0))
                    })
                return result

        elif report_type == "balance":
            # 资产负债表
            df = _pro.balancesheet(ts_code=ts_code, limit=4)
            if len(df) > 0:
                result = []
                for _, row in df.iterrows():
                    result.append({
                        "report_date": row.get('end_date', ''),
                        "total_assets": float(row.get('total_assets', 0)) / 10000,
                        "total_liabilities": float(row.get('total_liab', 0)) / 10000,
                        "total_equity": float(row.get('total_hldr_eqy_exc_min_int', 0)) / 10000,
                        "asset_liability_ratio": float(row.get('total_liab', 0)) / float(row.get('total_assets', 1)) * 100
                    })
                return result

        elif report_type == "cashflow":
            # 现金流量表
            df = _pro.cashflow(ts_code=ts_code, limit=4)
            if len(df) > 0:
                result = []
                for _, row in df.iterrows():
                    result.append({
                        "report_date": row.get('end_date', ''),
                        "operating_cashflow": float(row.get('n_cashflow_act', 0)) / 10000,
                        "investing_cashflow": float(row.get('n_cashflow_inv_act', 0)) / 10000,
                        "financing_cashflow": float(row.get('n_cashflow_fnc_act', 0)) / 10000,
                        "free_cashflow": float(row.get('free_cashflow', 0)) / 10000
                    })
                return result

    except Exception as e:
        logger.error(f"❌ Tushare 获取财报失败：{e}")

    return []


def get_consensus_estimates(code: str) -> dict:
    """
    获取一致预期数据（分析师预测）
    返回：EPS预测、营收预测、分析师数量
    """
    if not _ensure_tushare():
        return {}

    try:
        ts_code = _convert_code(code)
        df = _pro.forecast(ts_code=ts_code, limit=1)

        if len(df) > 0:
            row = df.iloc[0]
            return {
                "code": code,
                "report_date": row.get('end_date', ''),
                "net_profit_forecast": float(row.get('p_change_min', 0)),  # 预测净利润变动下限
                "eps_forecast": float(row.get('eps_forecast', 0)),
                "analyst_count": int(row.get('notice_count', 0))
            }
    except Exception as e:
        logger.error(f"❌ Tushare 获取一致预期失败：{e}")

    return {}


def get_industry_peers(code: str, max_peers: int = 10) -> list:
    """
    获取同行业公司
    返回：同行业股票列表
    """
    if not _ensure_tushare():
        return []

    try:
        ts_code = _convert_code(code)

        # 1. 获取股票所属行业
        df_basic = _pro.stock_basic(ts_code=ts_code, fields='ts_code,name,industry')
        if len(df_basic) == 0:
            return []

        industry = df_basic.iloc[0]['industry']

        # 2. 获取同行业其他股票
        df_peers = _pro.stock_basic(
            exchange='',
            list_status='L',
            fields='ts_code,name,industry,market'
        )

        # 筛选同行业股票
        peers = df_peers[df_peers['industry'] == industry]
        peers = peers[peers['ts_code'] != ts_code]  # 排除自己

        result = []
        for _, row in peers.head(max_peers).iterrows():
            result.append({
                "code": row['ts_code'],
                "name": row['name'],
                "industry": row['industry'],
                "market": row.get('market', '')
            })

        return result

    except Exception as e:
        logger.error(f"❌ Tushare 获取同行业公司失败：{e}")

    return []


def get_stock_basic(code: str) -> dict:
    """
    获取股票基本信息
    返回：股票名称、行业、上市日期等
    """
    if not _ensure_tushare():
        return {}

    try:
        ts_code = _convert_code(code)
        df = _pro.stock_basic(
            ts_code=ts_code,
            fields='ts_code,name,industry,market,list_date'
        )

        if len(df) > 0:
            row = df.iloc[0]
            return {
                "code": row['ts_code'],
                "name": row['name'],
                "industry": row.get('industry', ''),
                "market": row.get('market', ''),
                "list_date": row.get('list_date', '')
            }
    except Exception as e:
        logger.error(f"❌ Tushare 获取股票基本信息失败：{e}")

    return {}


# ---- CLI ----

if __name__ == "__main__":
    import sys
    import json
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Tushare Pro 数据获取")
    parser.add_argument("--action", required=True, choices=[
        "connect", "snapshot", "financials", "consensus", "peers", "basic"
    ])
    parser.add_argument("--code", help="股票代码")
    parser.add_argument("--report-type", default="income", help="财报类型")
    parser.add_argument("--max-peers", type=int, default=10, help="可比公司数量")

    args = parser.parse_args()

    if args.action == "connect":
        print(json.dumps(check_connection(), ensure_ascii=False, indent=2))

    elif args.action == "snapshot":
        if not args.code:
            print(json.dumps({"error": "需要提供 --code 参数"}, ensure_ascii=False))
            sys.exit(1)
        result = get_stock_snapshot(args.code)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.action == "financials":
        if not args.code:
            print(json.dumps({"error": "需要提供 --code 参数"}, ensure_ascii=False))
            sys.exit(1)
        result = get_financials(args.code, args.report_type)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.action == "consensus":
        if not args.code:
            print(json.dumps({"error": "需要提供 --code 参数"}, ensure_ascii=False))
            sys.exit(1)
        result = get_consensus_estimates(args.code)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.action == "peers":
        if not args.code:
            print(json.dumps({"error": "需要提供 --code 参数"}, ensure_ascii=False))
            sys.exit(1)
        result = get_industry_peers(args.code, args.max_peers)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.action == "basic":
        if not args.code:
            print(json.dumps({"error": "需要提供 --code 参数"}, ensure_ascii=False))
            sys.exit(1)
        result = get_stock_basic(args.code)
        print(json.dumps(result, ensure_ascii=False, indent=2))

"""
Wind 数据获取模块
封装 WindPy SDK，提供与 stock_data.py 对齐的数据接口。
Wind 数据质量远高于 AkShare，尤其在电话会议、一致预期、完整财报、行业对比方面。

需要 Wind API 终端登录状态。连接失败时返回 None，由 stock_data.py 自动降级到 AkShare。

独立CLI脚本，无内部依赖
用法:
  python3 wind_data.py --action connect
  python3 wind_data.py --action stock --code 300750.SZ
  python3 wind_data.py --action financials --code 600519.SH
  python3 wind_data.py --action consensus --code 300750.SZ
  python3 wind_data.py --action industry-peers --code 300750.SZ
"""

import argparse
import json
import sys
from datetime import datetime, timedelta

# ---- Wind 连接管理 ----
_wind_started = False


def _ensure_wind():
    """延迟启动 Wind 连接，只在真正需要时连接，带重试机制"""
    global _wind_started
    if _wind_started:
        return True
    try:
        from WindPy import w
        # 增加超时时间到30秒，并添加重试机制
        max_retries = 2
        for attempt in range(max_retries):
            ec = w.start(waitTime=30)
            if ec.ErrorCode == 0:
                _wind_started = w.isconnected()
                return _wind_started
            if attempt < max_retries - 1:
                import time
                time.sleep(2)  # 重试前等待2秒
        return False
    except Exception:
        return False


def _wind_code(code: str) -> str:
    """
    将 6 位 A股代码补齐交易所后缀。
    600xxx/601xxx/603xxx/605xxx/688xxx → .SH
    000xxx/001xxx/002xxx/003xxx/300xxx/301xxx → .SZ
    """
    if "." in code:
        return code
    code = code.strip()
    if not code.isdigit() or len(code) != 6:
        return code
    if code.startswith(("600", "601", "603", "605", "688", "689")):
        return f"{code}.SH"
    if code.startswith(("000", "001", "002", "003", "300", "301")):
        return f"{code}.SZ"
    if code.startswith(("8", "9", "4")):
        return f"{code}.BJ"
    return code


def _wsd_to_dict(data, fields: list) -> list:
    """
    将 w.wsd 返回对象转换为 list[dict]。
    WindData.Data 的结构是 [[field1_values], [field2_values], ...]
    """
    if data.ErrorCode != 0 or not data.Data:
        return []
    result = []
    dates = data.Times if data.Times else []
    for i, dt in enumerate(dates):
        row = {"date": str(dt)}
        for j, field in enumerate(fields):
            # 增强空指针保护：检查 data.Data[j] 是否存在且非空
            if (j < len(data.Data) and
                data.Data[j] is not None and
                isinstance(data.Data[j], (list, tuple)) and
                i < len(data.Data[j])):
                val = data.Data[j][i]
                row[field] = val if val is not None else None
            else:
                row[field] = None
        result.append(row)
    return result


def _wss_to_dict(data, codes: list, fields: list) -> dict:
    """
    将 w.wss 返回对象（快照查询）转为 dict。
    单个code时返回 {field: value}，多个code时返回 {code: {field: value}}
    """
    if data.ErrorCode != 0 or not data.Data:
        return {}

    # 增强空指针保护
    if len(codes) == 1:
        result = {}
        for j in range(len(fields)):
            if (j < len(data.Data) and
                data.Data[j] is not None and
                isinstance(data.Data[j], (list, tuple)) and
                len(data.Data[j]) > 0):
                result[fields[j]] = data.Data[j][0]
            else:
                result[fields[j]] = None
        return result

    result = {}
    for i, code in enumerate(codes):
        code_data = {}
        for j in range(len(fields)):
            if (j < len(data.Data) and
                data.Data[j] is not None and
                isinstance(data.Data[j], (list, tuple)) and
                i < len(data.Data[j])):
                code_data[fields[j]] = data.Data[j][i]
            else:
                code_data[fields[j]] = None
        result[code] = code_data
    return result


# ---- 核心接口 ----

def check_connection() -> dict:
    """检查 Wind 连接状态"""
    ok = _ensure_wind()
    return {"connected": ok, "source": "wind" if ok else "unavailable"}


def get_stock_snapshot(code: str) -> dict:
    """
    获取个股基础快照：价格、市值、PE/PB/PS、ROE、股息率
    """
    if not _ensure_wind():
        return {}
    from WindPy import w
    wcode = _wind_code(code)
    # 移除有问题的字段：high_52wk_, low_52wk_, chg_pct (ErrorCode=-40522006)
    fields = ["sec_name", "close", "mkt_cap_ard", "pe_ttm", "pb_lf", "ps_ttm",
              "roe_ttm2", "dividendyield2"]
    data = w.wss(wcode, ",".join(fields))
    if data.ErrorCode != 0:
        return {}
    return _wss_to_dict(data, [wcode], fields)


def get_financials(code: str) -> list:
    """
    获取完整三大报表（最近4个报告期）
    营收/净利润/毛利率/净利率/ROE/ROA/资产负债率/经营性现金流
    """
    if not _ensure_wind():
        return []
    from WindPy import w
    wcode = _wind_code(code)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=450)).strftime("%Y-%m-%d")

    # 利润表 + 资产负债表 + 现金流量表核心字段
    fields = [
        "oper_rev",           # 营业收入
        "np_belongto_parcomsh",  # 归母净利润
        "yoy_or",             # 营收同比
        "yoynetprofit",       # 净利润同比
        "grossprofitmargin",  # 毛利率
        "netprofitmargin",    # 净利率
        "roe_ttm2",           # ROE_TTM
        "roa_ttm2",           # ROA_TTM
        "debttoassets",       # 资产负债率
        "ocftodebt",          # 经营现金流/负债
        "ocf_to_or",          # 经营现金流/营收
        "cur_ratio",          # 流动比率
    ]
    data = w.wsd(wcode, ",".join(fields), start_date, end_date, "Period=Q;Days=Alldays")
    return _wsd_to_dict(data, fields)


def get_consensus_estimates(code: str) -> dict:
    """
    获取卖方一致预期（未来3年净利润预测 + 评级统计）
    这是 Wind 相比 AkShare 的杀手级能力。
    """
    if not _ensure_wind():
        return {}
    from WindPy import w
    wcode = _wind_code(code)
    fields = [
        "west_netprofit_FY1",   # 一致预期净利润 FY1
        "west_netprofit_FY2",   # FY2
        "west_netprofit_FY3",   # FY3
        "west_eps_FY1",         # 一致预期 EPS FY1
        "west_eps_FY2",
        "west_avgroe_FY1",      # 一致预期 ROE FY1
        "west_instnum",         # 覆盖机构数
        "rating_avg",           # 综合评级
        "rating_numofbuy",      # 买入数
        "rating_numofoutperform",  # 增持数
        "rating_numofhold",     # 中性数
        "rating_targetprice",   # 目标价均值
    ]
    data = w.wss(wcode, ",".join(fields))
    return _wss_to_dict(data, [wcode], fields)


def get_industry_peers(code: str, max_peers: int = 10) -> list:
    """
    获取同行业可比公司及其核心指标对比
    """
    if not _ensure_wind():
        return []
    from WindPy import w
    wcode = _wind_code(code)

    # 先获取该股票所属的申万三级行业
    ind_data = w.wss(wcode, "industry_sw_2021")
    if ind_data.ErrorCode != 0 or not ind_data.Data:
        return []
    industry = ind_data.Data[0][0] if ind_data.Data[0] else None
    if not industry:
        return []

    # 获取同行业股票列表（申万三级分类）
    peer_data = w.wset("sectorconstituent", f"sectorid=a39901017d000000;field=wind_code,sec_name")
    if peer_data.ErrorCode != 0:
        return []

    peer_codes = peer_data.Data[0] if peer_data.Data else []
    if not peer_codes:
        return []

    # 批量获取同行指标
    fields = ["sec_name", "mkt_cap_ard", "pe_ttm", "pb_lf", "roe_ttm2", "oper_rev_ttm", "yoy_or"]
    peers_str = ",".join(peer_codes[:max_peers])
    metrics = w.wss(peers_str, ",".join(fields))
    if metrics.ErrorCode != 0:
        return []

    result = []
    for i, pcode in enumerate(peer_codes[:max_peers]):
        row = {"code": pcode}
        for j, field in enumerate(fields):
            if j < len(metrics.Data) and i < len(metrics.Data[j]):
                row[field] = metrics.Data[j][i]
        result.append(row)
    return result


def get_valuation_history(code: str) -> dict:
    """
    获取历史估值分位数（PE/PB的10年百分位，用于判断当前估值高低）
    """
    if not _ensure_wind():
        return {}
    from WindPy import w
    wcode = _wind_code(code)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=3650)).strftime("%Y-%m-%d")

    data = w.wsd(wcode, "pe_ttm,pb_lf", start_date, end_date, "Days=Weekdays")
    if data.ErrorCode != 0 or not data.Data:
        return {}

    pe_series = [x for x in data.Data[0] if x is not None and x > 0]
    pb_series = [x for x in data.Data[1] if x is not None and x > 0]

    if not pe_series or not pb_series:
        return {}

    def percentile(series, value):
        if not series:
            return None
        count = sum(1 for x in series if x <= value)
        return round(count / len(series) * 100, 2)

    current_pe = pe_series[-1]
    current_pb = pb_series[-1]
    pe_sorted = sorted(pe_series)
    pb_sorted = sorted(pb_series)

    return {
        "pe_current": current_pe,
        "pe_10y_percentile": percentile(pe_sorted, current_pe),
        "pe_10y_min": pe_sorted[0],
        "pe_10y_max": pe_sorted[-1],
        "pe_10y_median": pe_sorted[len(pe_sorted) // 2],
        "pb_current": current_pb,
        "pb_10y_percentile": percentile(pb_sorted, current_pb),
        "pb_10y_median": pb_sorted[len(pb_sorted) // 2],
    }


def get_major_shareholders(code: str) -> list:
    """
    获取前十大股东及持股变动
    """
    if not _ensure_wind():
        return []
    from WindPy import w
    wcode = _wind_code(code)
    end_date = datetime.now().strftime("%Y-%m-%d")
    data = w.wset("shareholder", f"windcode={wcode};reportdate={end_date};"
                  "field=shareholder_name,hold_num,hold_ratio,change_num,shareholder_type")
    if data.ErrorCode != 0 or not data.Data:
        return []

    fields = data.Fields
    result = []
    for i in range(len(data.Data[0]) if data.Data else 0):
        row = {fields[j].lower(): data.Data[j][i] for j in range(len(fields))}
        result.append(row)
    return result


def get_earnings_calendar(code: str, quarters_back: int = 4) -> list:
    """
    获取最近N个季度的财报披露日期和电话会议情况
    """
    if not _ensure_wind():
        return []
    from WindPy import w
    wcode = _wind_code(code)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=quarters_back * 100)).strftime("%Y-%m-%d")

    data = w.wsd(wcode, "stm_issuingdate,stm_predict_issuingdate", start_date, end_date, "Period=Q;Days=Alldays")
    return _wsd_to_dict(data, ["stm_issuingdate", "stm_predict_issuingdate"])


# ---- CLI ----

def main():
    parser = argparse.ArgumentParser(description="Wind 数据获取")
    parser.add_argument("--action", required=True, choices=[
        "connect", "stock", "financials", "consensus", "peers", "valuation",
        "shareholders", "calendar"
    ])
    parser.add_argument("--code", help="股票代码")
    parser.add_argument("--max-peers", type=int, default=10, help="可比公司数量")

    args = parser.parse_args()

    if args.action == "connect":
        print(json.dumps(check_connection(), ensure_ascii=False, indent=2))
        return

    if not args.code:
        print(json.dumps({"error": "--code 是必填参数"}, ensure_ascii=False))
        sys.exit(1)

    actions = {
        "stock": lambda: get_stock_snapshot(args.code),
        "financials": lambda: get_financials(args.code),
        "consensus": lambda: get_consensus_estimates(args.code),
        "peers": lambda: get_industry_peers(args.code, args.max_peers),
        "valuation": lambda: get_valuation_history(args.code),
        "shareholders": lambda: get_major_shareholders(args.code),
        "calendar": lambda: get_earnings_calendar(args.code),
    }

    result = actions[args.action]()
    if not result:
        print(json.dumps({
            "success": False,
            "message": "Wind 连接失败或查询无结果。请确认 Wind API 终端已登录。"
        }, ensure_ascii=False))
    else:
        print(json.dumps({
            "success": True,
            "source": "wind",
            "code": args.code,
            "data": result
        }, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

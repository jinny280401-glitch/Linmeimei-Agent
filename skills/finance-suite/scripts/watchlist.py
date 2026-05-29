"""
自选股管理模块
管理个人股票自选清单，支持增删改查、批量行情监控、变动提醒。
持久化存储到 ~/.finance-suite/watchlist.json

独立CLI脚本，无内部依赖
用法:
  python3 watchlist.py --action add --code 300750 --name "宁德时代"
  python3 watchlist.py --action add --code 300750 --name "宁德时代" --tags "锂电池,储能" --alert-above 220 --alert-below 180
  python3 watchlist.py --action remove --code 300750
  python3 watchlist.py --action list
  python3 watchlist.py --action monitor
  python3 watchlist.py --action update-research --code 300750 --mode company --findings "..." --promises "..."
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# ---- 存储路径 ----
WATCHLIST_DIR = Path.home() / ".finance-suite"
WATCHLIST_FILE = WATCHLIST_DIR / "watchlist.json"


def _ensure_dir():
    WATCHLIST_DIR.mkdir(parents=True, exist_ok=True)


def _load() -> dict:
    _ensure_dir()
    if WATCHLIST_FILE.exists():
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"stocks": [], "updated_at": None}


def _save(data: dict):
    _ensure_dir()
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _find_stock(data, code):
    for s in data["stocks"]:
        if s["code"] == code:
            return s
    return None


# ---- 操作 ----

def action_add(args):
    data = _load()
    existing = _find_stock(data, args.code)
    if existing:
        print(json.dumps({"success": False, "message": f"{args.code} ({existing['name']}) 已在自选中"}, ensure_ascii=False))
        return

    stock = {
        "code": args.code,
        "name": args.name or args.code,
        "market": "A",
        "add_date": datetime.now().strftime("%Y-%m-%d"),
        "add_price": None,
        "tags": [t.strip() for t in args.tags.split(",")] if args.tags else [],
        "last_research_date": None,
        "research_history": [],
        "alerts": {}
    }

    # 尝试获取当前价格
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == args.code]
        if not row.empty:
            stock["add_price"] = float(row.iloc[0].get("最新价", 0))
    except Exception:
        pass

    if args.alert_above:
        stock["alerts"]["price_above"] = float(args.alert_above)
    if args.alert_below:
        stock["alerts"]["price_below"] = float(args.alert_below)
    if args.alert_change:
        stock["alerts"]["change_pct"] = float(args.alert_change)

    data["stocks"].append(stock)
    _save(data)
    print(json.dumps({
        "success": True,
        "message": f"已添加 {stock['name']}({stock['code']}) 到自选",
        "stock": stock
    }, ensure_ascii=False, indent=2))


def action_remove(args):
    data = _load()
    before = len(data["stocks"])
    data["stocks"] = [s for s in data["stocks"] if s["code"] != args.code]
    removed = before - len(data["stocks"])
    _save(data)
    print(json.dumps({
        "success": removed > 0,
        "message": f"已移除 {args.code}" if removed else f"{args.code} 不在自选中"
    }, ensure_ascii=False))


def action_list(args):
    data = _load()
    if not data["stocks"]:
        print(json.dumps({"count": 0, "stocks": [], "message": "自选清单为空"}, ensure_ascii=False))
        return

    summary = []
    for s in data["stocks"]:
        summary.append({
            "code": s["code"],
            "name": s["name"],
            "tags": s.get("tags", []),
            "add_date": s["add_date"],
            "add_price": s.get("add_price"),
            "last_research": s.get("last_research_date"),
            "research_count": len(s.get("research_history", [])),
            "alerts": s.get("alerts", {})
        })

    print(json.dumps({
        "count": len(summary),
        "updated_at": data.get("updated_at"),
        "stocks": summary
    }, ensure_ascii=False, indent=2))


def action_monitor(args):
    data = _load()
    if not data["stocks"]:
        print(json.dumps({"count": 0, "message": "自选清单为空，无法监控"}, ensure_ascii=False))
        return

    codes = [s["code"] for s in data["stocks"]]
    watchlist_map = {s["code"]: s for s in data["stocks"]}

    # 批量获取实时行情
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
    except Exception as e:
        print(json.dumps({"success": False, "error": f"获取行情失败: {e}"}, ensure_ascii=False))
        return

    results = []
    alerts_triggered = []

    for code in codes:
        row = df[df["代码"] == code]
        info = watchlist_map[code]

        if row.empty:
            results.append({
                "code": code, "name": info["name"],
                "status": "数据不可用"
            })
            continue

        r = row.iloc[0]
        price = float(r.get("最新价", 0))
        change_pct = float(r.get("涨跌幅", 0))
        volume = r.get("成交量")
        amount = r.get("成交额")
        pe = r.get("市盈率-动态")
        pb = r.get("市净率")

        # 计算持仓盈亏
        add_price = info.get("add_price")
        pnl_pct = round((price - add_price) / add_price * 100, 2) if add_price and add_price > 0 else None

        stock_result = {
            "code": code,
            "name": info["name"],
            "tags": info.get("tags", []),
            "price": price,
            "change_pct": round(change_pct, 2),
            "volume": volume,
            "amount": amount,
            "pe": pe,
            "pb": pb,
            "add_price": add_price,
            "pnl_pct": pnl_pct,
            "last_research": info.get("last_research_date"),
        }
        results.append(stock_result)

        # 检查提醒
        alert_cfg = info.get("alerts", {})
        if alert_cfg.get("price_above") and price >= alert_cfg["price_above"]:
            alerts_triggered.append(f"{info['name']}({code}) 突破 {alert_cfg['price_above']}，当前 {price}")
        if alert_cfg.get("price_below") and price <= alert_cfg["price_below"]:
            alerts_triggered.append(f"{info['name']}({code}) 跌破 {alert_cfg['price_below']}，当前 {price}")
        if alert_cfg.get("change_pct") and abs(change_pct) >= alert_cfg["change_pct"]:
            alerts_triggered.append(f"{info['name']}({code}) 涨跌幅 {change_pct:.2f}% 超过阈值 {alert_cfg['change_pct']}%")

    output = {
        "count": len(results),
        "monitor_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stocks": results,
    }
    if alerts_triggered:
        output["alerts_triggered"] = alerts_triggered

    print(json.dumps(output, ensure_ascii=False, indent=2))


def action_update_research(args):
    data = _load()
    stock = _find_stock(data, args.code)
    if not stock:
        print(json.dumps({"success": False, "message": f"{args.code} 不在自选中"}, ensure_ascii=False))
        return

    record = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "mode": args.mode or "company",
        "key_findings": args.findings or "",
        "management_promises": [p.strip() for p in args.promises.split(";")] if args.promises else []
    }
    stock["last_research_date"] = record["date"]
    stock.setdefault("research_history", []).append(record)
    _save(data)

    print(json.dumps({
        "success": True,
        "message": f"已更新 {stock['name']}({stock['code']}) 的研究记录",
        "research_count": len(stock["research_history"]),
        "latest_record": record
    }, ensure_ascii=False, indent=2))


def action_check_research(args):
    """检查某只股票是否有历史研究记录，用于增量研究判断"""
    data = _load()
    stock = _find_stock(data, args.code)
    if not stock:
        print(json.dumps({"in_watchlist": False, "has_research": False}, ensure_ascii=False))
        return

    history = stock.get("research_history", [])
    print(json.dumps({
        "in_watchlist": True,
        "has_research": len(history) > 0,
        "last_research_date": stock.get("last_research_date"),
        "research_count": len(history),
        "latest_findings": history[-1].get("key_findings", "") if history else "",
        "management_promises": history[-1].get("management_promises", []) if history else [],
        "tags": stock.get("tags", [])
    }, ensure_ascii=False, indent=2))


# ---- CLI ----

def main():
    parser = argparse.ArgumentParser(description="自选股管理")
    parser.add_argument("--action", required=True,
                        choices=["add", "remove", "list", "monitor", "update-research", "check-research"])
    parser.add_argument("--code", help="股票代码")
    parser.add_argument("--name", help="股票名称")
    parser.add_argument("--tags", help="标签，逗号分隔")
    parser.add_argument("--alert-above", type=float, help="价格上限提醒")
    parser.add_argument("--alert-below", type=float, help="价格下限提醒")
    parser.add_argument("--alert-change", type=float, help="涨跌幅阈值提醒(%)")
    parser.add_argument("--mode", help="研究模式: company/industry/combined")
    parser.add_argument("--findings", help="研究关键发现")
    parser.add_argument("--promises", help="管理层承诺，分号分隔")

    args = parser.parse_args()

    actions = {
        "add": action_add,
        "remove": action_remove,
        "list": action_list,
        "monitor": action_monitor,
        "update-research": action_update_research,
        "check-research": action_check_research,
    }

    if args.action in ("add",) and not args.code:
        print(json.dumps({"success": False, "error": "--code 是必填参数"}, ensure_ascii=False))
        sys.exit(1)
    if args.action in ("remove", "update-research", "check-research") and not args.code:
        print(json.dumps({"success": False, "error": "--code 是必填参数"}, ensure_ascii=False))
        sys.exit(1)

    actions[args.action](args)


if __name__ == "__main__":
    main()

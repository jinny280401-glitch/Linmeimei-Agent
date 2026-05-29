#!/usr/bin/env python3
"""
Finance Suite 工作流编排器
借鉴 ECC skills-first 架构，实现跨工具的组合分析流程

工作流：
  1. 晨间简报流 (Morning Brief) - 已实现
  2. 深度调研流 (Deep Dive) - TODO
  3. 量化信号流 (Quant Signal) - TODO

使用方式：
  python3 workflow_orchestrator.py --workflow morning-brief
  python3 workflow_orchestrator.py --workflow morning-brief --output brief.md
"""

import sys
import os
import json
import argparse
import asyncio
from datetime import datetime, date
from typing import Dict, List, Any
from math import isnan

# 确保能导入 scripts 目录下的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入各个数据脚本
try:
    from auction_data import get_auction_data
    from macro_data import get_macro_data
    from watchlist import _load as load_watchlist
except ImportError as e:
    print(f"❌ 导入失败: {e}", file=sys.stderr)
    sys.exit(1)


# ============================================================
# 工作流 1: 晨间简报流
# ============================================================

def workflow_morning_brief() -> Dict[str, Any]:
    """
    晨间简报流：集合竞价 → 自选股交叉 → 宏观快讯 → Markdown简报

    返回结构：
    {
        "workflow": "morning-brief",
        "timestamp": "2026-04-17 09:25:00",
        "market_pulse": {...},
        "watchlist_hits": [...],
        "macro_snapshot": {...},
        "brief_markdown": "..."
    }
    """
    print("🌅 开始执行晨间简报流...")
    result = {
        "workflow": "morning-brief",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # Step 1: 获取市场脉搏（涨停池、强势股、异动）
    print("📊 [1/3] 获取市场脉搏...")
    try:
        market_pulse = asyncio.run(get_auction_data())
        result["market_pulse"] = market_pulse
        print(f"  ✓ 涨停池: {len(market_pulse.get('涨停池', []))} 只")
        print(f"  ✓ 强势股: {len(market_pulse.get('强势股池', []))} 只")
    except Exception as e:
        print(f"  ✗ 市场脉搏获取失败: {e}")
        result["market_pulse"] = {"error": str(e)}

    # Step 2: 自选股交叉比对
    print("🎯 [2/3] 自选股交叉比对...")
    watchlist_hits = []
    try:
        watchlist_data = load_watchlist()
        watchlist = watchlist_data.get("stocks", [])
        if watchlist:
            limit_up_codes = {s.get("代码") for s in market_pulse.get("涨停池", [])}
            strong_codes = {s.get("代码") for s in market_pulse.get("强势股池", [])}

            for stock in watchlist:
                code = stock.get("code")
                name = stock.get("name", code)
                hit_type = []

                if code in limit_up_codes:
                    hit_type.append("涨停")
                if code in strong_codes:
                    hit_type.append("强势")

                if hit_type:
                    watchlist_hits.append({
                        "code": code,
                        "name": name,
                        "hit_type": hit_type,
                        "tags": stock.get("tags", [])
                    })

            print(f"  ✓ 自选股命中: {len(watchlist_hits)} 只")
            for hit in watchlist_hits:
                print(f"    - {hit['name']} ({hit['code']}): {', '.join(hit['hit_type'])}")
        else:
            print("  ⚠ 自选股为空")
    except Exception as e:
        print(f"  ✗ 自选股交叉失败: {e}")

    result["watchlist_hits"] = watchlist_hits

    # Step 3: 宏观快讯
    print("🌐 [3/3] 获取宏观快讯...")
    try:
        macro_snapshot = asyncio.run(get_macro_data())
        result["macro_snapshot"] = macro_snapshot

        # macro_snapshot 结构: {"gdp": [...], "cpi": [...], ...}
        gdp_list = macro_snapshot.get('gdp', [])
        cpi_list = macro_snapshot.get('cpi', [])

        gdp_latest = gdp_list[-1] if gdp_list else {}
        cpi_latest = cpi_list[-1] if cpi_list else {}

        def _v(val):
            try:
                return f"{float(val):.1f}" if val is not None and not isnan(float(val)) else "N/A"
            except (TypeError, ValueError):
                return "N/A"

        print(f"  ✓ GDP: {_v(gdp_latest.get('国内生产总值-同比增长'))}%")
        print(f"  ✓ CPI: {_v(cpi_latest.get('今值'))}%")
    except Exception as e:
        print(f"  ✗ 宏观数据获取失败: {e}")
        result["macro_snapshot"] = {"error": str(e)}

    # Step 4: 生成 Markdown 简报
    print("📝 生成简报...")
    brief_md = _generate_morning_brief_markdown(result)
    result["brief_markdown"] = brief_md

    print("✅ 晨间简报流完成")
    return result


def _generate_morning_brief_markdown(data: Dict[str, Any]) -> str:
    """生成晨间简报 Markdown"""
    timestamp = data.get("timestamp", "")
    market_pulse = data.get("market_pulse", {})
    watchlist_hits = data.get("watchlist_hits", [])
    macro = data.get("macro_snapshot", {})

    md = f"""# 📊 晨间简报 {timestamp}

## 🔥 市场脉搏

### 涨停池
"""

    limit_up = market_pulse.get("涨停池", [])[:10]  # 只显示前10只
    if limit_up:
        for stock in limit_up:
            md += f"- **{stock.get('名称')}** ({stock.get('代码')}) 涨停价: {stock.get('最新价', 'N/A')}\n"
    else:
        md += "暂无涨停股\n"

    md += "\n### 强势股\n"
    strong = market_pulse.get("强势股池", [])[:10]
    if strong:
        for stock in strong:
            md += f"- **{stock.get('名称')}** ({stock.get('代码')}) 涨幅: {stock.get('涨跌幅', 'N/A')}%\n"
    else:
        md += "暂无强势股\n"

    # 自选股命中
    md += "\n## 🎯 自选股命中\n"
    if watchlist_hits:
        for hit in watchlist_hits:
            tags_str = f" [{', '.join(hit['tags'])}]" if hit.get('tags') else ""
            md += f"- **{hit['name']}** ({hit['code']}): {', '.join(hit['hit_type'])}{tags_str}\n"
    else:
        md += "今日无自选股命中涨停池或强势股\n"

    # 宏观快讯
    md += "\n## 🌐 宏观快讯\n"
    if "error" not in macro:
        gdp_list = macro.get("gdp") or []
        cpi_list = macro.get("cpi") or []
        pmi_list = macro.get("pmi") or []

        def _fmt(v):
            """安全格式化数值，处理 nan 和 None"""
            if v is None:
                return "N/A"
            try:
                if isnan(float(v)):
                    return "N/A"
            except (TypeError, ValueError):
                pass
            return str(v)

        def _fmt_date(v):
            """安全格式化日期"""
            if isinstance(v, date):
                return v.strftime("%Y-%m")
            if v is None:
                return "N/A"
            return str(v)

        if gdp_list:
            g = gdp_list[-1]
            val = g.get('国内生产总值-同比增长')
            md += f"- **GDP 同比增长**: {_fmt(val)}% ({g.get('季度', 'N/A')})\n"
        if cpi_list:
            c = cpi_list[-1]
            val = c.get('今值')
            period = c.get('日期')
            md += f"- **CPI 月率**: {_fmt(val)}% ({_fmt_date(period)})\n"
        if pmi_list:
            p = pmi_list[-1]
            mfg = p.get('制造业-指数')
            non_mfg = p.get('非制造业-指数')
            period = p.get('月份', 'N/A')
            md += f"- **PMI 制造业/非制造业**: {_fmt(mfg)} / {_fmt(non_mfg)} ({period})\n"

        if not (gdp_list or cpi_list or pmi_list):
            md += "宏观数据暂不可用\n"
    else:
        md += "宏观数据暂不可用\n"

    md += "\n---\n*数据来源: 东方财富 (AkShare) | 生成时间: " + timestamp + "*\n"
    md += "*免责声明: 本简报仅供参考，不构成投资建议*\n"

    return md


# ============================================================
# 主程序
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Finance Suite 工作流编排器")
    parser.add_argument(
        "--workflow",
        choices=["morning-brief"],
        required=True,
        help="选择工作流"
    )
    parser.add_argument(
        "--output",
        help="输出文件路径（Markdown格式）"
    )

    args = parser.parse_args()

    # 执行工作流
    if args.workflow == "morning-brief":
        result = workflow_morning_brief()
    else:
        print(f"❌ 未知工作流: {args.workflow}", file=sys.stderr)
        sys.exit(1)

    # 输出结果
    if args.output:
        # 保存 Markdown 到文件
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result.get("brief_markdown", ""))
        print(f"\n✅ 报告已保存到: {args.output}")
    else:
        # 输出到终端
        print("\n" + "="*60)
        print(result.get("brief_markdown", ""))
        print("="*60)


if __name__ == "__main__":
    main()

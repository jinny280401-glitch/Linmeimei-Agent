"""意图路由 — 根据消息内容匹配技能模块"""

import os
import logging
from app.config import settings

logger = logging.getLogger(__name__)

# 技能路由表：(关键词列表, 技能名称, SKILL.md 相对路径)
SKILL_ROUTES = [
    # 金融投研
    (
        ["看票", "分析股票", "个股", "股票代码", "帮我看一下"],
        "stock-analyst",
        "skills/finance-suite/prompts/stock-analyst.md",
    ),
    (
        ["宏观", "内参", "经济形势", "GDP", "CPI", "PMI"],
        "macro-advisor",
        "skills/finance-suite/prompts/macro-advisor.md",
    ),
    (
        ["行业分析", "行业报告", "行业研究"],
        "industry-report",
        "skills/finance-suite/prompts/industry-report.md",
    ),
    (
        ["集合竞价", "涨停", "选股", "龙虎榜"],
        "auction-analysis",
        "skills/finance-suite/prompts/auction-analysis.md",
    ),
    (
        ["拆解视频", "视频总结", "视频分析", "逐字稿"],
        "video-breakdown",
        "skills/finance-suite/prompts/video-breakdown.md",
    ),
    (
        ["咨询报告", "麦肯锡", "会议纪要", "战略分析"],
        "mckinsey-report",
        "skills/finance-suite/prompts/mckinsey-report.md",
    ),

    # 销售军师
    (
        ["客户问", "怎么回答", "话术", "客户说", "怎么应对",
         "客户异议", "客户质疑", "怎么解释", "怎么说服", "推荐理由"],
        "sales-advisor",
        "skills/sales-advisor/SKILL.md",
    ),

    # 客户沙盘推演
    (
        ["客户分析", "客户排序", "开发优先级", "沙盘", "客户画像",
         "客户盘点", "哪个客户先跟", "盘客户", "客户开发", "客户梳理"],
        "client-sandbox",
        "skills/client-sandbox/SKILL.md",
    ),

    # 上市公司业务匹配
    (
        ["拜访准备", "业务匹配", "合作方向", "拜访公司", "董秘",
         "机构拜访", "BD准备", "对接上市公司"],
        "company-matcher",
        "skills/company-matcher/SKILL.md",
    ),
]


def match_skill(message: str) -> tuple[str, str]:
    """根据消息内容匹配技能

    Returns:
        (skill_name, skill_prompt) — 未匹配到返回 ("chat", "")
    """
    for keywords, skill_name, prompt_path in SKILL_ROUTES:
        if any(kw in message for kw in keywords):
            # 读取技能 Prompt
            full_path = os.path.join(settings.workspace_dir, "..", prompt_path)
            skill_prompt = ""
            try:
                with open(full_path, "r") as f:
                    skill_prompt = f.read()
            except FileNotFoundError:
                # 尝试 workspace 下的 skills 目录
                alt_path = os.path.join(settings.workspace_dir, prompt_path)
                try:
                    with open(alt_path, "r") as f:
                        skill_prompt = f.read()
                except FileNotFoundError:
                    logger.warning("Skill prompt not found: %s", prompt_path)

            logger.info("Matched skill: %s (keyword hit in message)", skill_name)
            return skill_name, skill_prompt

    return "chat", ""

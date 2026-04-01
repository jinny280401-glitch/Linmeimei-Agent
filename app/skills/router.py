"""意图路由 — 根据消息内容匹配技能模块"""

import os
import logging
from dataclasses import dataclass
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SkillMatch:
    name: str
    prompt: str
    use_plan: bool


# 技能路由表：(关键词列表, 技能名称, SKILL.md 路径, 是否用 plan 模式)
SKILL_ROUTES = [
    # 金融投研（复杂分析用 plan 模式）
    (["看票", "分析股票", "个股", "股票代码", "帮我看一下"],
     "stock-analyst", "skills/finance-suite/prompts/stock-analyst.md", True),

    (["宏观", "内参", "经济形势", "GDP", "CPI", "PMI"],
     "macro-advisor", "skills/finance-suite/prompts/macro-advisor.md", True),

    (["行业分析", "行业报告", "行业研究"],
     "industry-report", "skills/finance-suite/prompts/industry-report.md", True),

    (["集合竞价", "涨停", "选股", "龙虎榜"],
     "auction-analysis", "skills/finance-suite/prompts/auction-analysis.md", False),

    (["拆解视频", "视频总结", "视频分析", "逐字稿"],
     "video-breakdown", "skills/finance-suite/prompts/video-breakdown.md", True),

    (["咨询报告", "麦肯锡", "会议纪要", "战略分析"],
     "mckinsey-report", "skills/finance-suite/prompts/mckinsey-report.md", True),

    # 销售军师（实时场景，要快，不用 plan）
    (["客户问", "怎么回答", "话术", "客户说", "怎么应对",
      "客户异议", "客户质疑", "怎么解释", "怎么说服", "推荐理由"],
     "sales-advisor", "skills/sales-advisor/SKILL.md", False),

    # 客户沙盘推演（复杂分析用 plan）
    (["客户分析", "客户排序", "开发优先级", "沙盘", "客户画像",
      "客户盘点", "哪个客户先跟", "盘客户", "客户开发", "客户梳理"],
     "client-sandbox", "skills/client-sandbox/SKILL.md", True),

    # 上市公司业务匹配（复杂分析用 plan）
    (["拜访准备", "业务匹配", "合作方向", "拜访公司", "董秘",
      "机构拜访", "BD准备", "对接上市公司"],
     "company-matcher", "skills/company-matcher/SKILL.md", True),
]


def match_skill(message: str) -> SkillMatch:
    """根据消息内容匹配技能

    Returns:
        SkillMatch 对象，未匹配到返回 name="chat"
    """
    for keywords, skill_name, prompt_path, use_plan in SKILL_ROUTES:
        if any(kw in message for kw in keywords):
            skill_prompt = _load_prompt(prompt_path)
            logger.info("Matched skill: %s (plan=%s)", skill_name, use_plan)
            return SkillMatch(name=skill_name, prompt=skill_prompt, use_plan=use_plan)

    return SkillMatch(name="chat", prompt="", use_plan=False)


def _load_prompt(prompt_path: str) -> str:
    """加载技能 Prompt 文件"""
    for base in [os.path.join(settings.workspace_dir, ".."), settings.workspace_dir]:
        full_path = os.path.join(base, prompt_path)
        try:
            with open(full_path, "r") as f:
                return f.read()
        except FileNotFoundError:
            continue
    logger.warning("Skill prompt not found: %s", prompt_path)
    return ""

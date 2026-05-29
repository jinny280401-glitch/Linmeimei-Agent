"""Research skeleton schema for editorial research pages.

The skeleton is a navigation structure, not an investment decision framework.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchSection:
    section_id: str
    title: str
    prompt: str


RESEARCH_SKELETON: tuple[ResearchSection, ...] = (
    ResearchSection("00", "行业速览", "用少量事实说明行业边界、产业链位置和当前周期。"),
    ResearchSection("01", "公司定位", "说明公司在产业链中的角色、主要市场和差异化来源。"),
    ResearchSection("02", "收入结构/业务板块", "拆解收入来源、板块贡献和业务口径。"),
    ResearchSection("03", "核心产品与业务详情", "列出核心产品、交付方式、应用场景和关键约束。"),
    ResearchSection("04", "客户结构", "说明客户类型、集中度、合作稳定性和议价关系。"),
    ResearchSection("05", "竞争格局", "梳理主要参与者、竞争维度和结构变化。"),
    ResearchSection("06", "行业环境", "记录政策、供需、成本、价格和技术周期。"),
    ResearchSection("07", "增长变量", "列出可能影响经营结果的关键变量和观察指标。"),
    ResearchSection("08", "关键风险", "列出需要跟踪的经营、财务、行业与治理风险。"),
    ResearchSection("09", "言行一致：管理层承诺 vs 实际兑现", "对照管理层公开表述、行动和结果。"),
    ResearchSection("10", "情景推演", "搭建多情景研究路径，明确变量而非给出结论。"),
)


def default_research_skeleton() -> list[dict[str, str]]:
    """Return the standard 00-10 research map."""
    return [
        {
            "section_id": section.section_id,
            "title": section.title,
            "prompt": section.prompt,
            "status": "empty_slot",
        }
        for section in RESEARCH_SKELETON
    ]


def skeleton_ids() -> list[str]:
    return [section.section_id for section in RESEARCH_SKELETON]

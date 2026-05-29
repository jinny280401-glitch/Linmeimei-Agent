"""Editorial blocks for Research Editorial Layer v0."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from research_skeleton_schema import default_research_skeleton


@dataclass(frozen=True)
class HeroSummaryBlock:
    title: str
    report_date: str
    data_sources: list[str]
    research_scope: str
    disclaimer: str = "本页只提供研究导航和事实核对路径，不构成投资建议。"
    block_type: str = "hero_summary"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.block_type,
            "title": self.title,
            "report_date": self.report_date,
            "data_sources": self.data_sources,
            "research_scope": self.research_scope,
            "disclaimer": self.disclaimer,
        }


@dataclass(frozen=True)
class ResearchMapBlock:
    sections: list[dict[str, Any]]
    block_type: str = "research_map"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.block_type, "sections": self.sections}


@dataclass(frozen=True)
class BigNumbersBlock:
    items: list[dict[str, Any]] = field(default_factory=list)
    block_type: str = "big_numbers"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.block_type, "items": self.items}


@dataclass(frozen=True)
class CoreContradictionsBlock:
    items: list[dict[str, Any]] = field(default_factory=list)
    block_type: str = "core_contradictions"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.block_type, "items": self.items}


@dataclass(frozen=True)
class RiskBoxBlock:
    items: list[str] = field(default_factory=list)
    block_type: str = "risk_box"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.block_type, "items": self.items}


@dataclass(frozen=True)
class SoWhatBlock:
    items: list[str] = field(default_factory=list)
    block_type: str = "so_what"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.block_type, "items": self.items}


@dataclass(frozen=True)
class TimelineBlock:
    items: list[dict[str, Any]] = field(default_factory=list)
    block_type: str = "timeline"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.block_type, "items": self.items}


def build_research_hero_page(
    *,
    title: str,
    report_date: str,
    data_sources: list[str],
    research_scope: str,
    skeleton: list[dict[str, Any]] | None = None,
    big_numbers: list[dict[str, Any]] | None = None,
    core_contradictions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a navigation-only hero page JSON for a research report."""
    sections = skeleton or default_research_skeleton()
    hero = HeroSummaryBlock(
        title=title,
        report_date=report_date,
        data_sources=data_sources,
        research_scope=research_scope,
    )
    research_map = ResearchMapBlock(sections=sections)
    numbers = BigNumbersBlock(items=big_numbers or [])
    contradictions = CoreContradictionsBlock(items=core_contradictions or [])
    risk_box = RiskBoxBlock(items=[
        "信息来源可能存在滞后或口径差异",
        "行业供需、成本和政策变量需要持续复核",
        "管理层表述需要和后续经营结果交叉验证",
    ])
    so_what = SoWhatBlock(items=[
        "先明确研究问题，再进入正文材料收集",
        "优先核对收入结构、客户结构和增长变量",
        "把情景变量拆开观察，不在 Hero 页给出结论",
    ])
    timeline = TimelineBlock(items=[
        {"label": "资料收集", "status": "todo"},
        {"label": "事实核验", "status": "todo"},
        {"label": "正文撰写", "status": "not_started"},
    ])

    return {
        "title": title,
        "report_date": report_date or date.today().isoformat(),
        "data_sources": data_sources,
        "research_scope": research_scope,
        "page_type": "research_hero",
        "editorial_layer": "v0",
        "hero_summary": hero.to_dict(),
        "research_map": research_map.to_dict(),
        "blocks": [
            hero.to_dict(),
            research_map.to_dict(),
            numbers.to_dict(),
            contradictions.to_dict(),
            risk_box.to_dict(),
            so_what.to_dict(),
            timeline.to_dict(),
        ],
        "qc": {
            "status": "success",
            "sources": data_sources,
            "missing_sections": [],
            "body_generated": False,
            "advice_fields_present": False,
        },
    }


def demo_hero_for_symbol(symbol: str) -> dict[str, Any]:
    normalized = symbol.strip().upper()
    names = {
        "300750.SZ": "宁德时代研究导航",
        "600519.SH": "贵州茅台研究导航",
    }
    return build_research_hero_page(
        title=names.get(normalized, f"{normalized} 研究导航"),
        report_date=date.today().isoformat(),
        data_sources=["公开资料", "公司公告", "行业资料", "Finance Suite 本地研究缓存"],
        research_scope=f"{normalized} 企业与行业研究骨架",
        skeleton=default_research_skeleton(),
        big_numbers=[
            {"label": "研究章节", "value": "00-10", "note": "只定义导航，不生成正文"},
            {"label": "页面用途", "value": "Hero", "note": "用于进入研究而非形成结论"},
        ],
        core_contradictions=[
            {"topic": "规模扩张与盈利质量", "question": "收入增长、毛利率和现金流是否同步改善"},
            {"topic": "技术迭代与资本开支", "question": "投入节奏和产品周期是否匹配"},
        ],
    )

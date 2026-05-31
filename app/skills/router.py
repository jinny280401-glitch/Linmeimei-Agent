"""意图路由 — 根据消息内容匹配技能模块"""

import os
import json
import logging
import asyncio
from dataclasses import dataclass
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

# 意图分类标签
INTENT_LABELS = [
    "stock_analysis",    # 股票分析、个股查询
    "macro_research",    # 宏观经济、内参
    "industry_report",   # 行业分析报告
    "auction_analysis",  # 集合竞价、涨停分析
    "video_breakdown",   # 视频拆解、总结
    "mckinsey_report",   # 咨询报告、会议纪要
    "sales_support",     # 销售话术、客户应对
    "customer_analysis", # 客户分析、沙盘
    "company_matching",  # 上市公司业务匹配
    "chitchat",          # 闲聊、寒暄
    "unknown",           # 无法识别
]

INTENT_DESCRIPTIONS = "\n".join([f"- {label}" for label in INTENT_LABELS])


@dataclass
class SkillMatch:
    name: str
    prompt: str
    use_plan: bool


@dataclass
class IntentClassification:
    label: str
    confidence: float  # 0.0 ~ 1.0
    reasoning: str  # 分类理由（用于日志）


class IntentClassifier:
    """LLM 意图分类器 — 第一层路由

    在关键词匹配之前，先用 LLM 做语义分类。
    分类结果写入 consciousness 日志，供后续分析。
    """

    CLASSIFIER_PROMPT = """你是一个金融投研助手的内容分类专家。请分析用户输入，判断其真实意图。

可选标签：
{descriptions}

分析要求：
1. 仔细理解用户的真实需求，而非字面关键词
2. 如果用户用比喻或口语化表达（如"看看最近有啥机会"），要识别出背后的股票分析意图
3. 置信度反映你对判断的确信程度：0.0-1.0

输出格式（仅输出 JSON，不要其他内容）：
{{"label": "标签名", "confidence": 0.95, "reasoning": "判断理由（15字内）"}}

用户输入：{user_input}"""

    def __init__(self):
        self._label_set = set(INTENT_LABELS)

    async def classify(self, user_input: str) -> IntentClassification:
        """调用 Claude 对用户输入做意图分类"""
        prompt = self.CLASSIFIER_PROMPT.format(
            descriptions=INTENT_DESCRIPTIONS,
            user_input=user_input,
        )

        try:
            result = await self._call_claude(prompt)
            return self._parse_result(result, user_input)
        except Exception as e:
            logger.warning("Intent classification failed, falling back to keyword: %s", e)
            return IntentClassification(label="unknown", confidence=0.0, reasoning="分类器异常")

    def _parse_result(self, raw: str, user_input: str) -> IntentClassification:
        """解析分类结果"""
        try:
            data = json.loads(raw)
            label = data.get("label", "unknown")
            if label not in self._label_set:
                label = "unknown"
            return IntentClassification(
                label=label,
                confidence=data.get("confidence", 0.5),
                reasoning=data.get("reasoning", ""),
            )
        except json.JSONDecodeError:
            # 降级：用关键词匹配兜底
            return IntentClassification(
                label="unknown",
                confidence=0.0,
                reasoning=f"JSON解析失败: {raw[:50]}",
            )

    async def _call_claude(self, prompt: str) -> str:
        """调用 Claude CLI 进行分类"""
        cmd = [
            "claude",
            "--print",
            "--output-format", "json",
            "--max-turns", "1",
            prompt,
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=15.0,
        )
        if process.returncode != 0:
            raise RuntimeError(f"Claude error: {stderr.decode().strip()}")
        raw = stdout.decode().strip()
        data = json.loads(raw)
        return data.get("result", "")


# 全局单例（延迟初始化）
_classifier: Optional[IntentClassifier] = None


def get_classifier() -> IntentClassifier:
    """获取意图分类器单例"""
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier


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


# 意图标签 → 技能名称 映射
INTENT_TO_SKILL = {
    "stock_analysis": ("stock-analyst", True),
    "macro_research": ("macro-advisor", True),
    "industry_report": ("industry-report", True),
    "auction_analysis": ("auction-analysis", False),
    "video_breakdown": ("video-breakdown", True),
    "mckinsey_report": ("mckinsey-report", True),
    "sales_support": ("sales-advisor", False),
    "customer_analysis": ("client-sandbox", True),
    "company_matching": ("company-matcher", True),
}


async def match_skill_async(message: str, user_id: str = "system") -> tuple[SkillMatch, IntentClassification]:
    """异步意图路由 — LLM 分类 + 技能匹配

    第一层：IntentClassifier 用 LLM 语义分类
    第二层：根据分类结果映射到技能

    Returns:
        (SkillMatch, IntentClassification) 元组
    """
    classifier = get_classifier()
    intent = await classifier.classify(message)

    logger.info(
        "Intent classified: label=%s, confidence=%.2f, reasoning=%s, user_id=%s",
        intent.label, intent.confidence, intent.reasoning, user_id,
    )

    # 查表：意图 → 技能
    if intent.label in INTENT_TO_SKILL:
        skill_name, use_plan = INTENT_TO_SKILL[intent.label]
        # 找到对应的 prompt 路径
        for keywords, name, prompt_path, plan in SKILL_ROUTES:
            if name == skill_name:
                skill_prompt = _load_prompt(prompt_path)
                return (
                    SkillMatch(name=skill_name, prompt=skill_prompt, use_plan=use_plan),
                    intent,
                )

    # 兜底：关键词匹配
    fallback = match_skill(message)
    return fallback, intent


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

"""
digest_llm.py — 可插拔 LLM wrapper for research_digest

设计原则：
- 没有 API Key 时返回规则化 fallback 摘要，不阻塞 market_intel 主流程
- batch 模式：批量脱水，默认 Haiku 4.5（快+便宜）
- deep 模式：深度解读，默认 Sonnet 4.5
- 优先级：环境变量 OPENROUTER_API_KEY > ANTHROPIC_API_KEY > fallback

返回字段固定，无论哪条路径都保证 schema 一致：
{
  "core_logic":    str  (一句话核心逻辑)
  "catalysts":     [str] (催化因素 0-3 条)
  "risks":         [str] (风险点 0-3 条)
  "summary":       str  (整体摘要 50-150 字)
  "engine":        str  ("haiku" | "sonnet" | "fallback")
}
"""

from __future__ import annotations
import json
import os
import re
import logging
from typing import Literal

logger = logging.getLogger("finance-suite.digest_llm")

Mode = Literal["batch", "deep"]

_MODEL_MAP = {
    "batch": "anthropic/claude-haiku-4.5",
    "deep":  "anthropic/claude-sonnet-4.5",
}

_SYSTEM = (
    "你是 A 股卖方研报的脱水分析师。从给定的研报标题、机构、评级、行业、"
    "盈利预测信息中，提取核心投资逻辑、催化因素和风险点。"
    "输出严格 JSON，不要解释，不要 markdown。"
    "字段：core_logic(一句话核心逻辑,30字内)、catalysts(催化因素数组,0-3条,每条10字内)、"
    "risks(风险点数组,0-3条,每条10字内)、summary(整体摘要,50-150字)。"
    "信息不足以判断时，对应字段返回空字符串或空数组，不要编造。"
)


def _empty_result(engine: str = "fallback") -> dict:
    return {
        "core_logic": "",
        "catalysts": [],
        "risks": [],
        "summary": "",
        "engine": engine,
    }


def _fallback_summary(report: dict) -> dict:
    """无 LLM 时的规则化兜底：从结构化字段拼一个像样的摘要。"""
    title = report.get("title", "")
    broker = report.get("broker", "")
    rating = report.get("rating", "")
    rating_change = report.get("rating_change", "")
    industry = report.get("industry", "")
    target_price = report.get("target_price", "")

    parts = []
    if broker and rating:
        parts.append(f"{broker}给予{rating}评级")
        if rating_change and rating_change not in ("维持", "—", ""):
            parts.append(f"评级{rating_change}")
    if target_price:
        parts.append(f"目标价{target_price}")
    if industry:
        parts.append(f"所属{industry}")

    summary = "；".join(parts) if parts else title

    catalysts = []
    risks = []
    title_l = title.lower()
    pos_kw = ["增长", "新高", "突破", "拓展", "扩产", "受益", "上调", "向好", "复苏"]
    neg_kw = ["下滑", "承压", "下调", "风险", "压力"]
    for kw in pos_kw:
        if kw in title:
            catalysts.append(f"标题提及『{kw}』")
            break
    for kw in neg_kw:
        if kw in title:
            risks.append(f"标题提及『{kw}』")
            break

    return {
        "core_logic": title[:30],
        "catalysts": catalysts,
        "risks": risks,
        "summary": summary or "（无法生成摘要）",
        "engine": "fallback",
    }


def _build_user_prompt(report: dict) -> str:
    fields = [
        f"标题: {report.get('title','')}",
        f"机构: {report.get('broker','')}",
        f"评级: {report.get('rating','')}（变动: {report.get('rating_change','')}）",
        f"行业: {report.get('industry','')}",
        f"股票: {report.get('stock_name','')}({report.get('stock_code','')})",
    ]
    if report.get("target_price"):
        fields.append(f"目标价: {report['target_price']}")
    if report.get("eps_forecast"):
        fields.append(f"盈利预测: {report['eps_forecast']}")
    return "\n".join(fields)


def _call_openrouter(model: str, system: str, user: str, *, timeout: int = 20) -> dict | None:
    """调用 OpenRouter；失败返回 None。"""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None
    try:
        import requests
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": 400,
                "temperature": 0.2,
            },
            timeout=timeout,
        )
        if resp.status_code != 200:
            logger.warning(f"openrouter http {resp.status_code}: {resp.text[:200]}")
            return None
        content = resp.json()["choices"][0]["message"]["content"]
        return _parse_json_loose(content)
    except Exception as e:
        logger.warning(f"openrouter call failed: {e}")
        return None


def _call_anthropic(model_short: str, system: str, user: str, *, timeout: int = 20) -> dict | None:
    """调用 Anthropic 原生 API；失败返回 None。"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import requests
        model = "claude-haiku-4-5-20251001" if model_short == "batch" else "claude-sonnet-4-5"
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 400,
                "system": system,
                "messages": [{"role": "user", "content": user}],
                "temperature": 0.2,
            },
            timeout=timeout,
        )
        if resp.status_code != 200:
            logger.warning(f"anthropic http {resp.status_code}: {resp.text[:200]}")
            return None
        content = resp.json()["content"][0]["text"]
        return _parse_json_loose(content)
    except Exception as e:
        logger.warning(f"anthropic call failed: {e}")
        return None


def _parse_json_loose(text: str) -> dict | None:
    """LLM 输出可能带 markdown 代码块，宽松解析。"""
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def summarize_report(report: dict, mode: Mode = "batch") -> dict:
    """单篇脱水。无 API Key 自动 fallback。

    Args:
        report: 必含 title；可选 broker/rating/rating_change/industry/stock_name/
                stock_code/target_price/eps_forecast
        mode:   batch (Haiku) | deep (Sonnet)
    """
    if not report.get("title"):
        return _empty_result("fallback")

    system = _SYSTEM
    user = _build_user_prompt(report)

    # 优先 OpenRouter（按混合策略走 Haiku/Sonnet）
    parsed = _call_openrouter(_MODEL_MAP[mode], system, user)
    engine = "haiku" if mode == "batch" else "sonnet"

    # 退路：Anthropic 原生
    if parsed is None:
        parsed = _call_anthropic(mode, system, user)

    # 最终兜底：规则化
    if parsed is None:
        return _fallback_summary(report)

    # 字段归一
    return {
        "core_logic": str(parsed.get("core_logic", ""))[:60],
        "catalysts": [str(x)[:30] for x in (parsed.get("catalysts") or [])][:3],
        "risks": [str(x)[:30] for x in (parsed.get("risks") or [])][:3],
        "summary": str(parsed.get("summary", ""))[:300],
        "engine": engine,
    }


def summarize_batch(reports: list[dict], mode: Mode = "batch") -> list[dict]:
    """批量脱水。当前为串行实现（v1），未来可换并发。"""
    out = []
    for r in reports:
        try:
            out.append(summarize_report(r, mode=mode))
        except Exception as e:
            logger.warning(f"summarize fail on {r.get('title','?')}: {e}")
            out.append(_fallback_summary(r))
    return out

"""LLM 评估器 — Agent 回复质量监控

LLM-as-Judge 模式：
- 每次 Agent 回复后，调用 Claude 对回复打分
- 维度：准确性（accuracy）、完整性（completeness）、可操作性（actionability）
- 分数存入用户 SQLite，供统计分析
- 低分触发重试（最多 2 次）

参考企业级 Agent 的 Evaluator-optimizer 系统设计。
"""

import json
import logging
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """评估结果"""
    accuracy: float      # 准确性 0-1
    completeness: float  # 完整性 0-1
    actionability: float  # 可操作性 0-1
    overall: float       # 综合分数 0-1
    reasoning: str       # 评分理由
    passed: bool         # 是否通过（overall >= threshold）


class Evaluator:
    """LLM 评估器"""

    EVAL_PROMPT = """你是一个金融投研助手的内容质量评审。请对以下回复打分。

评分维度（每项 0-1）：
1. 准确性（accuracy）：信息是否正确？有无事实错误或幻觉？
2. 完整性（completeness）：是否完整回答了用户问题？有无遗漏关键信息？
3. 可操作性（actionability）：对用户是否有实际帮助？能否指导具体行动？

输出格式（仅输出 JSON，不要其他内容）：
{{"accuracy": 0.9, "completeness": 0.8, "actionability": 0.85, "overall": 0.85, "reasoning": "评分理由（30字内）"}}

---
用户问题：{user_input}
---
回复内容：{response}"""

    # 通过阈值
    THRESHOLD = 0.6

    def __init__(self, threshold: float = THRESHOLD):
        self.threshold = threshold

    async def evaluate(
        self,
        user_input: str,
        response: str,
    ) -> EvaluationResult:
        """对回复进行评估"""
        if not response or len(response.strip()) < 10:
            return EvaluationResult(
                accuracy=0.0,
                completeness=0.0,
                actionability=0.0,
                overall=0.0,
                reasoning="回复过短，无法评估",
                passed=False,
            )

        prompt = self.EVAL_PROMPT.format(
            user_input=user_input[:500],  # 限制长度
            response=response[:2000],
        )

        try:
            raw = await self._call_claude(prompt)
            return self._parse_result(raw)
        except Exception as e:
            logger.warning("Evaluation failed: %s", e)
            # 降级：返回通过，不阻断流程
            return EvaluationResult(
                accuracy=0.5,
                completeness=0.5,
                actionability=0.5,
                overall=0.5,
                reasoning=f"评估器异常: {e}",
                passed=True,
            )

    def _parse_result(self, raw: str) -> EvaluationResult:
        """解析评估结果"""
        try:
            data = json.loads(raw)
            overall = data.get("overall", 0.5)
            return EvaluationResult(
                accuracy=data.get("accuracy", 0.5),
                completeness=data.get("completeness", 0.5),
                actionability=data.get("actionability", 0.5),
                overall=overall,
                reasoning=data.get("reasoning", ""),
                passed=overall >= self.threshold,
            )
        except json.JSONDecodeError:
            return EvaluationResult(
                accuracy=0.5,
                completeness=0.5,
                actionability=0.5,
                overall=0.5,
                reasoning="JSON解析失败",
                passed=True,
            )

    async def _call_claude(self, prompt: str) -> str:
        """调用 Claude CLI 进行评估"""
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
            timeout=20.0,
        )
        if process.returncode != 0:
            raise RuntimeError(f"Claude error: {stderr.decode().strip()}")
        raw = stdout.decode().strip()
        data = json.loads(raw)
        return data.get("result", "")


# 全局单例
_evaluator: Optional[Evaluator] = None


def get_evaluator() -> Evaluator:
    """获取评估器单例"""
    global _evaluator
    if _evaluator is None:
        _evaluator = Evaluator()
    return _evaluator
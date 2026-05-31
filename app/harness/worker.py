"""Worker 基类 — Orchestrator-Workers 模式的任务执行器

Worker 职责：
- 执行具体的子任务（选股、宏观分析、行业研究等）
- 调用 ask_claude_with_evaluation 获取带评估的回复
- 返回 SubTaskResult

设计原则：
- Worker 可热插拔，新增技能只需注册即可
- 每个 Worker 复用现有技能模块的 prompt 和数据脚本
"""

import time
import json
import logging
import asyncio
from dataclasses import dataclass, asdict
from typing import Optional, Dict
from app.services.agent import ask_claude_with_evaluation
from app.services.evaluator import EvaluationResult

logger = logging.getLogger(__name__)


@dataclass
class SubTask:
    """子任务描述"""
    id: str
    description: str          # 子任务描述
    worker_type: str          # worker 类型：macro-advisor / stock-analyst / etc
    prompt_suffix: str = ""    # 追加到 Worker 的额外指令


@dataclass
class SubTaskResult:
    """子任务执行结果"""
    task_id: str
    worker_type: str
    response: str
    eval_accuracy: float = 0.0
    eval_completeness: float = 0.0
    eval_actionability: float = 0.0
    eval_overall: float = 0.0
    eval_reasoning: str = ""
    duration_ms: int = 0
    error: str = ""


class Worker:
    """Worker 基类"""

    def __init__(self, worker_type: str, skill_name: str, skill_prompt: str, use_plan: bool = True):
        self.worker_type = worker_type
        self.skill_name = skill_name
        self.skill_prompt = skill_prompt
        self.use_plan = use_plan

    async def execute(self, task: SubTask, system_prompt: str, user_id: str) -> SubTaskResult:
        """执行子任务"""
        start_time = time.time()
        task_id = task.id

        try:
            logger.info("Worker %s executing task %s", self.worker_type, task_id)

            # 拼接完整 prompt
            full_prompt = f"{task.description}\n\n{task.prompt_suffix}".strip()

            # 调用 Agent（带评估）
            response, _, eval_result = await ask_claude_with_evaluation(
                prompt=full_prompt,
                system_prompt=system_prompt,
                user_id=user_id,
                max_retries=1,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            return SubTaskResult(
                task_id=task_id,
                worker_type=self.worker_type,
                response=response,
                eval_accuracy=eval_result.accuracy,
                eval_completeness=eval_result.completeness,
                eval_actionability=eval_result.actionability,
                eval_overall=eval_result.overall,
                eval_reasoning=eval_result.reasoning,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning("Worker %s task %s failed: %s", self.worker_type, task_id, str(e))
            return SubTaskResult(
                task_id=task_id,
                worker_type=self.worker_type,
                response="",
                error=str(e),
                duration_ms=duration_ms,
            )


class WorkerRegistry:
    """Worker 注册表 — 管理所有可用的 Worker"""

    def __init__(self):
        self._workers: Dict[str, Worker] = {}

    def register(self, worker_type: str, skill_name: str, skill_prompt: str, use_plan: bool = True):
        """注册一个 Worker"""
        self._workers[worker_type] = Worker(worker_type, skill_name, skill_prompt, use_plan)
        logger.info("Worker registered: %s -> %s", worker_type, skill_name)

    def get(self, worker_type: str) -> Optional[Worker]:
        """获取 Worker"""
        return self._workers.get(worker_type)

    def list_types(self) -> list[str]:
        """列出所有 Worker 类型"""
        return list(self._workers.keys())


# 全局 Worker 注册表
_worker_registry: Optional[WorkerRegistry] = None


def get_worker_registry() -> WorkerRegistry:
    """获取 Worker 注册表单例"""
    global _worker_registry
    if _worker_registry is None:
        _worker_registry = WorkerRegistry()
        _register_default_workers(_worker_registry)
    return _worker_registry


def _register_default_workers(registry: WorkerRegistry):
    """注册默认的 Workers — 复用现有技能模块"""
    # 宏观分析 Worker
    registry.register(
        worker_type="macro-advisor",
        skill_name="macro-advisor",
        skill_prompt="",  # 由 engine 在运行时注入
        use_plan=True,
    )

    # 股票分析 Worker
    registry.register(
        worker_type="stock-analyst",
        skill_name="stock-analyst",
        skill_prompt="",
        use_plan=True,
    )

    # 行业研究 Worker
    registry.register(
        worker_type="industry-report",
        skill_name="industry-report",
        skill_prompt="",
        use_plan=True,
    )

    # 销售军师 Worker
    registry.register(
        worker_type="sales-advisor",
        skill_name="sales-advisor",
        skill_prompt="",
        use_plan=False,
    )

    # 客户沙盘 Worker
    registry.register(
        worker_type="client-sandbox",
        skill_name="client-sandbox",
        skill_prompt="",
        use_plan=True,
    )

    # 上市公司匹配 Worker
    registry.register(
        worker_type="company-matcher",
        skill_name="company-matcher",
        skill_prompt="",
        use_plan=True,
    )

    logger.info("Default workers registered: %s", registry.list_types())
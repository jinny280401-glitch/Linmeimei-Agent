"""意识流日志 — Agent 的内心独白

参考 KAIROS 的追加模式日志：
- 不是聊天记录（那在 SQLite 里）
- 是 Agent 的每次决策过程记录
- 用于调试回溯：当林妹妹回复不恰当时，回溯她的"思考过程"

日志类型：
- tick: 定时心跳触发的思考
- message: 收到用户消息触发的处理
- action: 主动执行的动作
- error: 错误和恢复过程
- compact: AutoCompact 压缩记录
"""

import os
import json
import logging
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ConsciousnessEntry:
    """一条意识流记录"""
    time: str
    trigger: str        # tick / message / action / error / compact
    user_id: str        # 相关用户（"system" 表示系统级）
    thought: str        # 思考内容
    action: str = ""    # 执行的动作
    result: str = ""    # 动作结果
    skill: str = ""     # 使用的技能
    duration_ms: int = 0  # 耗时


class ConsciousnessStream:
    """意识流日志管理器 — 追加写入，永不覆盖"""

    def __init__(self, log_dir: str):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

    def _get_log_path(self) -> str:
        """按日期分文件"""
        date = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.log_dir, f"consciousness_{date}.jsonl")

    def log(
        self,
        trigger: str,
        thought: str,
        user_id: str = "system",
        action: str = "",
        result: str = "",
        skill: str = "",
        duration_ms: int = 0,
    ):
        """记录一条意识流"""
        entry = ConsciousnessEntry(
            time=datetime.now().isoformat(),
            trigger=trigger,
            user_id=user_id,
            thought=thought,
            action=action,
            result=result,
            skill=skill,
            duration_ms=duration_ms,
        )

        log_path = self._get_log_path()
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        except Exception:
            logger.exception("Failed to write consciousness log")

    def log_message(self, user_id: str, thought: str, skill: str = "", duration_ms: int = 0):
        """记录消息处理的思考过程"""
        self.log("message", thought, user_id=user_id, skill=skill, duration_ms=duration_ms)

    def log_error(self, user_id: str, error: str, recovery: str = ""):
        """记录错误和恢复"""
        self.log("error", error, user_id=user_id, action="recovery", result=recovery)

    def log_compact(self, user_id: str, compacted_count: int, summary_len: int):
        """记录 AutoCompact 操作"""
        self.log(
            "compact",
            f"Compressed {compacted_count} messages, summary {summary_len} chars",
            user_id=user_id,
        )

    def get_recent(self, limit: int = 50) -> list[dict]:
        """读取最近的意识流记录（调试用）"""
        log_path = self._get_log_path()
        if not os.path.exists(log_path):
            return []
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            entries = []
            for line in lines[-limit:]:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
            return entries
        except Exception:
            logger.exception("Failed to read consciousness log")
            return []

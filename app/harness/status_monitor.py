"""状态监控系统 — 参考 Claude HUD 实现

职责：
1. 解析 Claude Code transcript JSONL（工具调用、子代理、Token 用量）
2. 追踪 MCP 工具调用频率和成功率（finance-suite 8个工具）
3. 记录到 consciousness 日志系统
4. 提供实时状态查询接口

设计原则：
- 增量解析：只读 transcript 新增行，避免重复解析
- 异步非阻塞：不影响主流程性能
- 数据降级：解析失败不影响 Agent 正常工作
"""

import os
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolCallStats:
    """工具调用统计"""
    tool_name: str
    total_calls: int = 0
    success_calls: int = 0
    failed_calls: int = 0
    avg_duration_ms: float = 0.0
    last_call_time: str = ""


@dataclass
class AgentStats:
    """子代理统计"""
    agent_type: str
    status: str  # running / completed / failed
    duration_ms: int = 0
    start_time: str = ""


@dataclass
class SessionStats:
    """会话统计"""
    user_id: str
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    tool_calls: dict[str, ToolCallStats] = field(default_factory=dict)
    active_agents: list[AgentStats] = field(default_factory=list)
    last_update: str = ""


class StatusMonitor:
    """状态监控器 — 解析 transcript 并追踪状态"""

    def __init__(self, consciousness_stream):
        self.consciousness = consciousness_stream
        # 每用户的会话统计
        self._sessions: dict[str, SessionStats] = {}
        # transcript 文件偏移量（增量解析）
        self._transcript_offsets: dict[str, int] = {}
        # tool_id → tool_name 映射（用于匹配 tool_result）
        self._tool_id_map: dict[str, str] = {}

    def parse_transcript(self, transcript_path: str, user_id: str) -> Optional[SessionStats]:
        """增量解析 transcript JSONL

        Args:
            transcript_path: transcript 文件路径
            user_id: 用户 ID

        Returns:
            更新后的会话统计，解析失败返回 None
        """
        if not os.path.exists(transcript_path):
            return None

        try:
            # 获取当前偏移量
            offset = self._transcript_offsets.get(transcript_path, 0)

            # 获取或创建会话统计
            if user_id not in self._sessions:
                self._sessions[user_id] = SessionStats(user_id=user_id)
            stats = self._sessions[user_id]

            with open(transcript_path, "r", encoding="utf-8") as f:
                # 跳到上次读取位置
                f.seek(offset)

                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                        self._process_entry(entry, stats)
                    except json.JSONDecodeError:
                        logger.warning("Invalid JSON in transcript: %s", line[:100])
                        continue

                # 更新偏移量
                self._transcript_offsets[transcript_path] = f.tell()

            stats.last_update = datetime.now().isoformat()
            return stats

        except Exception as e:
            logger.error("Failed to parse transcript %s: %s", transcript_path, str(e))
            return None

    def _process_entry(self, entry: dict, stats: SessionStats):
        """处理单条 transcript 记录"""
        entry_type = entry.get("type")

        if entry_type == "tool_use":
            self._process_tool_use(entry, stats)
        elif entry_type == "tool_result":
            self._process_tool_result(entry, stats)
        elif entry_type == "usage":
            self._process_usage(entry, stats)
        elif entry_type == "agent_start":
            self._process_agent_start(entry, stats)
        elif entry_type == "agent_end":
            self._process_agent_end(entry, stats)

    def _process_tool_use(self, entry: dict, stats: SessionStats):
        """处理工具调用"""
        tool_name = entry.get("name", "unknown")
        tool_id = entry.get("id", "")

        if tool_name not in stats.tool_calls:
            stats.tool_calls[tool_name] = ToolCallStats(tool_name=tool_name)

        tool_stats = stats.tool_calls[tool_name]
        tool_stats.total_calls += 1
        tool_stats.last_call_time = datetime.now().isoformat()

        # 记录 tool_id → tool_name 映射
        if tool_id:
            self._tool_id_map[tool_id] = tool_name

        # 记录到 consciousness
        self.consciousness.log(
            trigger="tool_use",
            thought=f"调用工具: {tool_name}",
            user_id=stats.user_id,
            action=tool_name,
            result=f"tool_id={tool_id}",
        )

    def _process_tool_result(self, entry: dict, stats: SessionStats):
        """处理工具结果"""
        tool_id = entry.get("tool_use_id", "")
        is_error = entry.get("is_error", False)

        # 用 tool_id → tool_name 映射反查
        tool_name = self._tool_id_map.get(tool_id)
        if not tool_name or tool_name not in stats.tool_calls:
            return

        tool_stats = stats.tool_calls[tool_name]
        if is_error:
            tool_stats.failed_calls += 1
        else:
            tool_stats.success_calls += 1

    def _process_usage(self, entry: dict, stats: SessionStats):
        """处理 Token 用量"""
        usage = entry.get("usage", {})
        stats.input_tokens += usage.get("input_tokens", 0)
        stats.output_tokens += usage.get("output_tokens", 0)
        stats.cache_read_tokens += usage.get("cache_read_input_tokens", 0)
        stats.cache_write_tokens += usage.get("cache_creation_input_tokens", 0)
        stats.total_tokens = stats.input_tokens + stats.output_tokens

    def _process_agent_start(self, entry: dict, stats: SessionStats):
        """处理子代理启动"""
        agent_type = entry.get("agent_type", "unknown")
        agent_stats = AgentStats(
            agent_type=agent_type,
            status="running",
            start_time=datetime.now().isoformat(),
        )
        stats.active_agents.append(agent_stats)

        self.consciousness.log(
            trigger="agent_start",
            thought=f"启动子代理: {agent_type}",
            user_id=stats.user_id,
            action=agent_type,
        )

    def _process_agent_end(self, entry: dict, stats: SessionStats):
        """处理子代理结束"""
        agent_type = entry.get("agent_type", "unknown")
        duration_ms = entry.get("duration_ms", 0)

        # 更新对应的 agent 状态
        for agent in stats.active_agents:
            if agent.agent_type == agent_type and agent.status == "running":
                agent.status = "completed"
                agent.duration_ms = duration_ms
                break

        self.consciousness.log(
            trigger="agent_end",
            thought=f"子代理完成: {agent_type}",
            user_id=stats.user_id,
            action=agent_type,
            result=f"{duration_ms}ms",
            duration_ms=duration_ms,
        )

    def get_stats(self, user_id: str) -> Optional[SessionStats]:
        """获取用户的会话统计"""
        return self._sessions.get(user_id)

    def get_mcp_tool_summary(self, user_id: str) -> dict:
        """获取 MCP 工具调用摘要（finance-suite 专用）

        Returns:
            {
                "stock_analysis": {"calls": 10, "success_rate": 0.9},
                "market_pulse": {"calls": 5, "success_rate": 1.0},
                ...
            }
        """
        stats = self.get_stats(user_id)
        if not stats:
            return {}

        summary = {}
        for tool_name, tool_stats in stats.tool_calls.items():
            # 只统计 MCP 工具（以 mcp__ 开头）
            if not tool_name.startswith("mcp__"):
                continue

            success_rate = 0.0
            if tool_stats.total_calls > 0:
                success_rate = tool_stats.success_calls / tool_stats.total_calls

            summary[tool_name] = {
                "calls": tool_stats.total_calls,
                "success_rate": success_rate,
                "last_call": tool_stats.last_call_time,
            }

        return summary

    def reset_stats(self, user_id: str):
        """重置用户统计（新会话开始时）"""
        if user_id in self._sessions:
            del self._sessions[user_id]

        # 清理相关的 transcript 偏移量
        to_remove = [k for k in self._transcript_offsets.keys() if user_id in k]
        for key in to_remove:
            del self._transcript_offsets[key]

        # 清理 tool_id 映射（防止跨会话污染）
        self._tool_id_map.clear()

    def log_status_snapshot(self, user_id: str):
        """记录状态快照到 consciousness"""
        stats = self.get_stats(user_id)
        if not stats:
            return

        mcp_summary = self.get_mcp_tool_summary(user_id)
        active_agents = [a.agent_type for a in stats.active_agents if a.status == "running"]

        self.consciousness.log(
            trigger="status_snapshot",
            thought=f"Token: {stats.total_tokens} | MCP工具: {len(mcp_summary)} | 活跃代理: {len(active_agents)}",
            user_id=user_id,
            action="snapshot",
            result=json.dumps(mcp_summary, ensure_ascii=False),
        )

# 2026-04-17 更新日志：状态监控系统

## 概述

为林妹妹 Agent 和 Claude Code 添加实时状态监控能力，参考 Claude HUD 插件实现。

## 新增功能

### 1. 林妹妹 Agent 状态监控系统

**文件**: `app/harness/status_monitor.py`

**功能**:
- 增量解析 Claude Code transcript JSONL
- 追踪 MCP 工具调用统计（finance-suite 8个工具）
- 记录子代理状态和执行时长
- 统计 Token 用量（input/output/cache）
- 输出到 consciousness 日志系统

**核心类**:
```python
class StatusMonitor:
    def parse_transcript(transcript_path, user_id) -> SessionStats
    def get_mcp_tool_summary(user_id) -> dict
    def log_status_snapshot(user_id)
```

**数据结构**:
- `ToolCallStats`: 工具调用次数、成功率、平均耗时
- `AgentStats`: 子代理类型、状态、执行时长
- `SessionStats`: 会话级统计（Token、工具、代理）

**集成点**:
- `app/harness/engine.py` 的 `process_message()` 方法
- 每次消息处理后记录状态快照

### 2. Claude Code 实时状态面板

**配置文件**: `~/.claude/settings.json`

**安装方式**:
```json
{
  "enabledPlugins": {
    "claude-hud@jarrodwatts": true
  },
  "extraKnownMarketplaces": {
    "jarrodwatts": {
      "source": "github",
      "repo": "jarrodwatts/claude-hud"
    }
  }
}
```

**显示内容**:
- 上下文用量百分比（绿色<70%，黄色70-85%，红色>85%）
- 工具调用活动（最近使用的工具）
- 子代理状态（运行中/已完成）
- 订阅用量限制（5小时/7天）
- Git 状态、项目路径、模型名称

**更新频率**: 每 300ms 自动刷新

## 技术亮点

### 增量解析机制
```python
# 记录文件偏移量，只读新增行
self._transcript_offsets: dict[str, int] = {}
f.seek(offset)  # 跳到上次读取位置
```

### 数据降级策略
- 解析失败不影响 Agent 正常工作
- 异步非阻塞，不影响主流程性能
- 智能缓存，减少 I/O 操作

### 与 consciousness 日志集成
```python
self.consciousness.log(
    trigger="tool_use",
    thought=f"调用工具: {tool_name}",
    user_id=user_id,
    action=tool_name,
)
```

## 参考资料

- [Claude HUD GitHub](https://github.com/jarrodwatts/claude-hud)
- Claude Code statusLine API 文档
- transcript JSONL 格式规范

## 使用方法

### 林妹妹 Agent

状态监控已自动集成，无需额外配置。查看日志：

```bash
# 查看 consciousness 日志
tail -f data/consciousness/consciousness_2026-04-17.jsonl

# 查看 MCP 工具调用统计
grep "status_snapshot" data/consciousness/consciousness_2026-04-17.jsonl | jq .
```

### Claude Code

重启 Claude Code 后自动加载 Claude HUD 插件：

```bash
# 重启 Claude Code
claude
```

配置显示选项：

```bash
# 进入配置向导
/claude-hud:configure
```

## 下一步计划

- [ ] 添加 MCP 工具成功率告警（低于 80% 时通知）
- [ ] 实现状态监控 Web 仪表盘
- [ ] 集成到飞书通知（每日统计报告）
- [ ] 优化 transcript 解析性能（大文件场景）

## 相关文件

- `app/harness/status_monitor.py` - 状态监控核心
- `app/harness/engine.py` - 集成点
- `app/harness/consciousness.py` - 日志系统
- `~/.claude/settings.json` - Claude Code 配置
- `~/.claude/projects/-Users-Zhuanz/memory/reference_claude_hud.md` - 参考文档

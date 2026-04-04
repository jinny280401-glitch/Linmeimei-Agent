"""Harness 层 — Agent 的「身体」，永不下线的外壳

参考 Claude Code 架构：Harness 和 Agent 内核解耦。
- Harness：消息路由、错误恢复、上下文管理、日志 → 永远在线
- Agent 内核：LLM 调用、记忆检索、工具执行 → 可热替换
"""

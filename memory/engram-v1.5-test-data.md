# Engram v1.5 测试记忆（3 条）

## 测试记忆 JSON

### 记忆 1：客户偏好
```json
{
  "summary": "客户偏好",
  "domain": "customer_memory",
  "detail": "客户 ou_test001 偏好简短回复，不喜欢长篇大论",
  "source_agent": "林妹妹",
  "tags": ["customer:ou_test001"],
  "importance": "high"
}
```

### 记忆 2：投研结论
```json
{
  "summary": "投研结论",
  "domain": "finance_research",
  "detail": "中简科技（300777）碳纤维业务受益于国产替代，Q3 营收增长 45%",
  "source_agent": "林妹妹",
  "tags": ["A 股", "碳纤维", "中简科技"],
  "importance": "high"
}
```

### 记忆 3：业务规则
```json
{
  "summary": "业务规则",
  "domain": "sales_advisor",
  "detail": "客户分层：VIP 客户优先响应，普通客户排队处理",
  "source_agent": "林妹妹",
  "tags": ["客户分层", "优先级判断"],
  "importance": "critical"
}
```

---

## 验收重点

| # | 验收项 | 状态 |
|---|--------|------|
| 1 | 能写 3 条真实业务记忆 | ⏳ 待测 |
| 2 | 能按 `memory_type` 查出来 | ⏳ 待测 |
| 3 | 能按 `source_agent=林妹妹` 查出来 | ⏳ 待测 |
| 4 | 能按 `domain` 查出来 | ⏳ 待测 |
| 5 | `archive` 后默认查询不污染 `active` | ⏳ 待测 |
| 6 | `delete` 是软删除，不真删 | ⏳ 待测 |
| 7 | 旧 payload 兼容（v1 → v1.5 自动补全） | ⏳ 待测 |

---

## 执行方式

### 方式 1：运行测试脚本
```bash
# 在哥哥的 Mac 上执行
cd ~/.openclaw/workspace-linmeimei/memory
bash engram-v1.5-test-commands.sh
```

### 方式 2：单条 curl 测试
```bash
# 写入测试
curl -X POST \
  -H "X-API-Token: cfc1658c394cf411fedfdc4951a38d7b" \
  -H "Content-Type: application/json" \
  -d '{"summary": "客户偏好", "domain": "customer_memory", "detail": "测试内容", "source_agent": "林妹妹", "tags": ["customer:ou_test001"], "importance": "high"}' \
  http://127.0.0.1:8766/lessons

# 查询测试
curl -H "X-API-Token: cfc1658c394cf411fedfdc4951a38d7b" \
  "http://127.0.0.1:8766/lessons?source_agent=林妹妹&limit=10"
```

---

## 预期结果

### 写入测试
- 返回 200/201 状态码
- 返回包含记忆 ID

### 查询测试
- 按 `source_agent=林妹妹` → 返回 3 条
- 按 `domain=customer_memory` → 返回记忆 1
- 按 `domain=finance_research` → 返回记忆 2
- 按 `domain=sales_advisor` → 返回记忆 3
- 按 `tags=customer:ou_test001` → 返回记忆 1

### 归档测试
- 归档后默认查询 → 不返回已归档记忆
- `include_archived=true` → 返回已归档记忆

### 旧 payload 兼容
- 输入 v1 格式自动补全为 v1.5 格式
- 补全字段：`source_agent`、`status`、`memory_type`、`importance`、`retention_scope`

---

**准备完成时间**：2026-05-24 01:55  
**等待**：哥哥在 Mac 上执行测试

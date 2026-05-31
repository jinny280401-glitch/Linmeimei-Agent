# Engram v1.5 Schema 测试计划

## 负责人：林妹妹（使用侧验证）

## 职责
- 用新 schema 写 3 条真实记忆
- 跑通看是否能正确展示
- 检查客户话术/报告场景是否能读到正确记忆

---

## Schema 标准（v1.5 暂定）

### API 格式
- **写入**：`POST /lessons` 使用 JSON payload
- **读取**：`GET /memory` 支持过滤参数
- **不采用**：Markdown frontmatter（仅用于文档）

### POST /lessons 字段定义
```json
{
  "lesson": "记忆标题",
  "domain": "业务领域",
  "detail": "具体内容",
  "source_agent": "林妹妹",
  "memory_type": "customer_preference | research_conclusion | business_rule | progress | decision | bugfix | test",
  "importance": "critical | high | medium | low",
  "retention_scope": "permanent | 90d | 30d | 7d",
  "tags": ["客户", "Finance Suite"],
  "status": "active"
}
```

### GET /memory 过滤参数
- `domain` - 按业务领域过滤
- `source_agent` - 按来源 Agent 过滤
- `memory_type` - 按记忆类型过滤
- `status` - 按状态过滤（active/archived/deleted）
- `days` - 按时间范围过滤

### 客户维度处理
- **不强制**在 Engram v1.5 中加入客户维度字段
- 如需测试客户偏好，用 tags 方式：`"tags": ["customer:ou_xxx"]`
- `customers/{user_id}.md` = 客户档案文件（人工维护/展示）
- Engram = 跨 Agent 长期事实账本
- **本周不做双向同步**

---

## 验收重点（本轮）

- [ ] 能写 3 条真实业务记忆
- [ ] 能按 `memory_type` 查出来
- [ ] 能按 `source_agent=林妹妹` 查出来
- [ ] 能按 `domain` 查出来
- [ ] `archive` 后默认查询不污染 `active` 结果
- [ ] `delete` 是软删除，不真删
- [ ] 旧 payload 兼容（v1 → v1.5 自动补全字段）

---

## 测试记忆（3 条）

### 记忆 1：客户偏好
**domain**: `customer_memory`
**memory_type**: `customer_preference`
**tags**: `["customer:ou_test001"]`

**测试内容**：
- 客户称呼偏好
- 沟通风格偏好
- 关注领域

**验收**：
- 写入成功
- 按 `memory_type=customer_preference` 能查出
- 按 `tags` 能过滤出特定客户

---

### 记忆 2：投研分析结论
**domain**: `finance_research`
**memory_type**: `research_conclusion`
**tags**: `["A 股", "碳纤维", "中简科技"]`

**测试内容**：
- 公司：中简科技（300777）
- 核心观点：看多/看空/中性
- 关键逻辑（3-5 条）
- 风险点

**验收**：
- 写入成功
- 按 `domain=finance_research` 能查出
- 按 `source_agent=林妹妹` 能查出

---

### 记忆 3：业务规则
**domain**: `sales_advisor`
**memory_type**: `business_rule`
**importance**: `high`
**tags**: `["客户分层", "优先级判断"]`

**测试内容**：
- 规则类型：客户分层标准
- 规则内容：S/A/B/C 判断逻辑
- 适用场景：客户沙盘

**验收**：
- 写入成功
- 按 `memory_type=business_rule` 能查出
- 按 `importance=high` 能过滤

---

## 详细测试用例

### 写入测试
- [ ] POST /lessons 写入记忆 1（客户偏好）
- [ ] POST /lessons 写入记忆 2（投研结论）
- [ ] POST /lessons 写入记忆 3（业务规则）
- [ ] 验证返回状态码 200/201
- [ ] 验证返回包含记忆 ID

### 读取测试
- [ ] GET /memory?memory_type=customer_preference → 返回记忆 1
- [ ] GET /memory?memory_type=research_conclusion → 返回记忆 2
- [ ] GET /memory?memory_type=business_rule → 返回记忆 3
- [ ] GET /memory?source_agent=林妹妹 → 返回 3 条
- [ ] GET /memory?domain=customer_memory → 返回记忆 1
- [ ] GET /memory?domain=finance_research → 返回记忆 2
- [ ] GET /memory?domain=sales_advisor → 返回记忆 3

### 归档测试
- [ ] 对记忆 1 调用 archive 接口
- [ ] GET /memory（默认）→ 不返回记忆 1
- [ ] GET /memory?status=archived → 返回记忆 1
- [ ] GET /memory?status=active → 不返回记忆 1

### 软删除测试
- [ ] 对记忆 2 调用 delete 接口
- [ ] GET /memory（默认）→ 不返回记忆 2
- [ ] GET /memory?status=deleted → 返回记忆 2
- [ ] 确认数据库中记录仍存在（软删除）

### 兼容性验收
- [ ] 旧数据（MEMORY.md 格式）不受影响
- [ ] 新旧 schema 能共存

### 旧 payload 兼容测试（v1 → v1.5）

**输入（v1 格式）**：
```json
{
  "lesson": "旧格式测试",
  "domain": "legacy",
  "detail": "只有 v1 字段",
  "source_tool": "Claude"
}
```

**预期输出（v1.5 格式）**：
```json
{
  "lesson": "旧格式测试",
  "domain": "legacy",
  "detail": "只有 v1 字段",
  "source_tool": "Claude",
  "source_agent": "燿",        // 自动映射（根据 AADR-0005）
  "status": "active",          // 默认值
  "memory_type": "progress",   // 默认值
  "importance": "B",           // 默认值
  "retention_scope": "90d"     // 默认值
}
```

**测试步骤**：
- [ ] 用 v1 格式 POST /lessons
- [ ] 验证响应中包含自动补全的字段
- [ ] 验证 `source_tool` → `source_agent` 映射正确
- [ ] 验证默认值：`status=active`、`memory_type=progress`、`importance=B`、`retention_scope=90d`
- [ ] 用 GET /memory 能查到这条记录
- [ ] 用 GET /memory?source_agent=燿 能查到这条记录

---

## 依赖项

| 依赖 | 负责人 | 状态 |
|------|--------|------|
| Engram v1.5 schema 定义 | C（技术实现） | 待完成 |
| POST /lessons API 扩展 | C（技术实现） | 待完成 |
| GET /memory 过滤接口 | C（技术实现） | 待完成 |
| 软删除/归档接口 | C（技术实现） | 待完成 |

---

## Engram HTTP API 架构（已确认）

| 项目 | 值 |
|------|-----|
| 服务地址 | `http://127.0.0.1:8766` |
| Token 鉴权 | `cfc1658c394cf411fedfdc4951a38d7b` |
| 运行方式 | launchd 开机自启 |
| Claude Code | 通过 MCP 自动访问 |
| ChatGPT | 通过 Custom Instructions |
| 手动测试 | `curl + Token` |

---

## 备注

- 测试环境：OpenClaw workspace-linmeimei
- 测试时间：API 就绪后 1 天内完成
- 问题反馈方式：直接记录到本文件

---

**最后更新**：2026-05-24 01:51（补全旧 payload 兼容测试 + API 架构信息）

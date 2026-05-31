#!/bin/bash
# Engram v1.5 测试命令集
# 执行环境：哥哥的 Mac 本机（Engram API 运行在 http://127.0.0.1:8766）
# Token: cfc1658c394cf411fedfdc4951a38d7b

API_BASE="http://127.0.0.1:8766"
API_TOKEN="cfc1658c394cf411fedfdc4951a38d7b"

echo "=========================================="
echo "Engram v1.5 测试套件 - 林妹妹使用侧验证"
echo "=========================================="

# -------------------------------------------
# 测试 1：写入客户偏好
# -------------------------------------------
echo ""
echo "📝 测试 1：写入客户偏好..."
curl -X POST \
  -H "X-API-Token: $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "summary": "客户偏好",
    "domain": "customer_memory",
    "detail": "客户 ou_test001 偏好简短回复，不喜欢长篇大论",
    "source_agent": "林妹妹",
    "tags": ["customer:ou_test001"],
    "importance": "high"
  }' \
  "$API_BASE/lessons"
echo ""

# -------------------------------------------
# 测试 2：写入投研结论
# -------------------------------------------
echo ""
echo "📝 测试 2：写入投研结论..."
curl -X POST \
  -H "X-API-Token: $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "summary": "投研结论",
    "domain": "finance_research",
    "detail": "中简科技（300777）碳纤维业务受益于国产替代，Q3 营收增长 45%",
    "source_agent": "林妹妹",
    "tags": ["A 股", "碳纤维", "中简科技"],
    "importance": "high"
  }' \
  "$API_BASE/lessons"
echo ""

# -------------------------------------------
# 测试 3：写入业务规则
# -------------------------------------------
echo ""
echo "📝 测试 3：写入业务规则..."
curl -X POST \
  -H "X-API-Token: $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "summary": "业务规则",
    "domain": "sales_advisor",
    "detail": "客户分层：VIP 客户优先响应，普通客户排队处理",
    "source_agent": "林妹妹",
    "tags": ["客户分层", "优先级判断"],
    "importance": "critical"
  }' \
  "$API_BASE/lessons"
echo ""

# -------------------------------------------
# 测试 4：按 source_agent 查询
# -------------------------------------------
echo ""
echo "🔍 测试 4：按 source_agent=林妹妹 查询..."
curl -s -H "X-API-Token: $API_TOKEN" \
  "$API_BASE/lessons?source_agent=林妹妹&limit=10" | jq .
echo ""

# -------------------------------------------
# 测试 5：按 domain 查询
# -------------------------------------------
echo ""
echo "🔍 测试 5：按 domain=customer_memory 查询..."
curl -s -H "X-API-Token: $API_TOKEN" \
  "$API_BASE/lessons?domain=customer_memory" | jq .
echo ""

# -------------------------------------------
# 测试 6：按 tags 查询
# -------------------------------------------
echo ""
echo "🔍 测试 6：按 tags=customer:ou_test001 查询..."
curl -s -H "X-API-Token: $API_TOKEN" \
  "$API_BASE/lessons?tags=customer:ou_test001" | jq .
echo ""

# -------------------------------------------
# 测试 7：归档记忆
# -------------------------------------------
echo ""
echo "📦 测试 7：归档记忆..."
echo "先获取第一条记忆的 item_id..."
ITEM_ID=$(curl -s -H "X-API-Token: $API_TOKEN" \
  "$API_BASE/lessons?source_agent=林妹妹&limit=1" | jq -r '.items[0].id')
echo "获取到的 item_id: $ITEM_ID"

if [ "$ITEM_ID" != "null" ] && [ -n "$ITEM_ID" ]; then
  echo "执行归档..."
  curl -X POST \
    -H "X-API-Token: $API_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"reason": "测试归档", "status": "archived"}' \
    "$API_BASE/memory/$ITEM_ID/archive"
  echo ""
else
  echo "⚠️  未找到记忆，跳过归档测试"
fi
echo ""

# -------------------------------------------
# 测试 8：验证归档后查询不污染 active
# -------------------------------------------
echo ""
echo "🔍 测试 8：验证归档后查询..."
echo "默认查询（应不包含 archived）："
curl -s -H "X-API-Token: $API_TOKEN" \
  "$API_BASE/lessons?source_agent=林妹妹" | jq '.items | length'

echo "包含 archived 查询："
curl -s -H "X-API-Token: $API_TOKEN" \
  "$API_BASE/memory?source_agent=林妹妹&include_archived=true" | jq '.items | length'
echo ""

# -------------------------------------------
# 测试 9：旧 payload 兼容（v1 → v1.5）
# -------------------------------------------
echo ""
echo "🔄 测试 9：旧 payload 兼容测试..."
curl -X POST \
  -H "X-API-Token: $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "lesson": "旧格式测试",
    "domain": "legacy",
    "detail": "只有 v1 字段",
    "source_tool": "Claude"
  }' \
  "$API_BASE/lessons"
echo ""

echo "=========================================="
echo "测试套件执行完成"
echo "=========================================="

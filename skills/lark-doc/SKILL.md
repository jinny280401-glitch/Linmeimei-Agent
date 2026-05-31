---
name: lark-doc
description: 获取 Lark/飞书文档并转换为 Markdown。使用此功能从 Lark 文档中获取故障排除指南和操作说明。
---
# 飞书文档技能

此技能提供两项功能：

1. 获取一份飞书文档并将其内容转换为 Markdown 格式
2. 将故障排除摘要附在文档中，以便日后参考。

## 何时使用

**获取文档：**

- 用户需要故障排除步骤或操作指南。
- 在诊断问题前，请先查阅相关的操作说明。
- 当用户询问具体流程或分步指南时
- 关键词：故障排除、步骤、指南、流程、操作、修复方法

**附加摘要：**

- 完成故障排除会话后
- 当用户希望记录已解决的问题以供将来参考时
- 向指南文档中添加新的故障排除案例
- 关键词：保存、记录、文档、撰写摘要、添加至指南

## 如何使用

### 获取文档

```bash
python skills/lark-doc/fetch_doc.py
```

### 附加故障排除摘要

```bash
python skills/lark-doc/append_summary.py \
  -t "问题标题" \
  -p "问题描述" \
  -s '["排查步骤 1", "排查步骤 2", "排查步骤 3"]' \
  -o "解决方案" \
  -n "可选备注"
```

**参数：**

- `-t, --title` 故障排查案例标题（必填）
- `-p, --problem` 问题描述（必填）
- `-s, --steps` 已采取的故障排除步骤的 JSON 数组（必需）
- `-o, --solution` 解决该问题的方案（必填）
- `-n, --notes` 可选附加说明

## 环境变量

- `LARK_APP_ID` Lark 应用 ID
- `LARK_APP_SECRET` Lark 应用密钥
- `LARK_DOC_URL` 要获取或追加的 Lark 文档 URL
- `LARK_DOMAIN`（可选）企业飞书自定义域名

## 输出格式

### 获取文档

返回飞书文档的 Markdown 格式内容，包括：

- 标题（H1-H9）
- 文本段落
- 有序列表与无序列表
- 代码块
- 语录
- 待办事项（复选框）

### 附加摘要

返回包含成功状态的 JSON：

```json
{
  "success": true,
  "documentId": "xxx",
  "url": "https://...",
  "message": "Successfully appended troubleshooting summary: ..."
}
```

## 示例输出

### 已获取文档

```markdown
# Troubleshooting Guide

## Common Issues

### Issue 1: Service Not Starting

1. Check the logs
2. Verify configuration
3. Restart the service

### Issue 2: Connection Timeout

- Check network connectivity
- Verify firewall rules
```

### 附加摘要结构

摘要将按照以下结构附加到文档中：

```markdown
---

### 问题标题 (2025-01-15 14:30)

#### 问题描述

问题的详细描述...

#### 排查步骤

- 排查步骤 1
- 排查步骤 2
- 排查步骤 3

#### 解决方案

解决方案的详细说明...

#### 备注

可选的备注信息...
```

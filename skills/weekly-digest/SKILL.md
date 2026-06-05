---
name: weekly-digest
version: 1.0.0
description: >
  福建金融资讯周报生成器。抓取4类资讯（政策法规/金融同业/福建上市公司/省市属企业），
  LLM筛选后创建飞书文档并发送链接给触发者。
  触发条件：用户说"周报"、"生成周报"、"本周资讯"、"金融简报"。
author: LinMeiMei
license: MIT

metadata:
  openclaw:
    emoji: "📋"
    security_level: L2
    always: false
    requires:
      bins: [python3]
      env: [TAVILY_KEYS]
    network_behavior:
      makes_requests: true
      domains:
        - api.tavily.com
        - openrouter.ai
        - open.feishu.cn
        - www.feishu.cn
    env_declarations:
      - name: TAVILY_KEYS
        required: true
        description: Tavily API Key
      - name: FEISHU_APP_ID
        required: false
        description: 飞书应用 ID（已内置林妹妹 App 默认值）
      - name: FEISHU_APP_SECRET
        required: false
        description: 飞书应用 Secret
      - name: OPENROUTER_KEY
        required: false
        description: OpenRouter API Key（LLM筛选用）
---

# 福建金融资讯周报

## 触发条件

用户说以下任意内容时触发本技能：
- "周报"、"生成周报"、"出周报"
- "本周资讯"、"金融简报"、"资讯汇总"
- "帮我整理本周金融新闻"

## 使用方法

### 生成周报并发送文档链接给当前对话用户

```bash
# open_id 模式（飞书单聊）
python3 scripts/digest.py --receive-id <用户飞书open_id> --receive-type open_id

# chat_id 模式（飞书群聊）
python3 scripts/digest.py --receive-id <群chat_id> --receive-type chat_id

# 不传参数：发到默认群
python3 scripts/digest.py
```

## 工作流程

1. 并发搜索4类资讯（Tavily，过去7天）
2. LLM（OpenRouter Gemini Flash）筛选，剔除无效内容
3. 创建飞书 docx 文档，写入结构化内容
4. 将文档链接发回触发对话

## 输出格式

文档结构：
- 一、政策法规/监管动态
- 二、金融同业
- 三、上市公司
- 四、省市属企业

每条资讯包含：来源机构 + 标题 + 摘要 + 原文链接

## 注意事项

- 抓取耗时约 2-3 分钟，触发后告知用户稍等
- TAVILY_KEYS 使用 `.env` 中已有的值，无需额外配置
- 飞书 App 凭证已内置，权限已开通（docx:document 应用身份）

#!/usr/bin/env python3
"""
福建金融资讯周报 — 每周一早上自动抓取4类资讯，LLM筛选后推送飞书
"""

import os
import json
import time
import secrets
import logging
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── 日期解析与年份过滤 ─────────────────────────────────────────────────────────
def parse_date_year(date_str: str) -> int:
    """从日期字符串中提取年份"""
    import re
    if not date_str:
        return 0
    # 尝试多种格式
    patterns = [
        r'(\d{4})[年\-/]',  # 2026年、2026-、2026/
        r'^(\d{4})',         # 开头的四位数字
        r'20(\d{2})',        # 20XX格式
    ]
    for pattern in patterns:
        match = re.search(pattern, str(date_str))
        if match:
            year = int(match.group(1))
            if 2020 <= year <= 2030:
                return year
    return 0

def filter_by_year(items: list, target_year: int = 2026) -> list:
    """后处理：只保留指定年份的条目"""
    filtered = []
    for item in items:
        # 检查多个可能包含日期的字段
        year = 0
        for key in ['date', 'published_date', 'published', 'year']:
            if key in item:
                year = parse_date_year(str(item[key]))
                if year > 0:
                    break
        
        # 如果解析不出年份但有URL，尝试从URL提取
        if year == 0 and 'url' in item:
            year = parse_date_year(str(item['url']))
        
        # 只保留2026年的或无法解析年份的（可能是最新资讯）
        if year == 0 or year == target_year:
            filtered.append(item)
        else:
            logger.debug(f"过滤非2026年资讯: {year}年 - {item.get('title', '')[:30]}")
    
    return filtered


# ── API Keys ──────────────────────────────────────────────────────────────────
# 所有 API Keys 必须通过环境变量传入，不在代码中硬编码
TAVILY_KEY    = os.getenv("TAVILY_KEY")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
IWENCAI_KEY   = os.getenv("IWENCAI_API_KEY", "")
FEISHU_APP_ID     = os.getenv("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET")
# 默认回复到嘉勤服务群（林妹妹App下的chat_id）
FEISHU_DEFAULT_CHAT_ID = os.getenv("FEISHU_DEFAULT_CHAT_ID")

# ── 搜索查询配置 ──────────────────────────────────────────────────────────────
QUERIES = {
    "政策法规/监管动态": [
        "福建证监局 监管措施 行政处罚 2026",
        "福建金融监管局 通知 政策 2026",
        "福建省政府 金融 政策 文件 2026",
        "福建发改委 金融 债券 2026",
        "上交所 深交所 福建 上市公司 监管 2026",
        "证监会 福建 最新动态 2026",
    ],
    "金融同业": [
        "福建银行 战略合作协议 签署 2026",
        "福建券商 兴业证券 华福证券 业务 2026",
        "厦门银行 福建农商银行 最新动态 2026",
        "福建省内银行 创新业务 落地 2026",
        "福建券商 项目 承销 2026",
    ],
    "省市属企业": [
        "福建省国资委 省属企业 动态 2026",
        "福州国企 签约 投资 2026",
        "厦门国企 项目 合作 2026",
        "福建省属企业 最新消息 2026",
    ],
}

# 上市公司关键词（同花顺API用）
FUJIAN_LISTED_QUERIES = [
    "福建上市公司 股东减持 增持 2026",
    "福建上市公司 股份回购 2026",
    "福建上市公司 董事长 总经理 变更 2026",
    "福建上市公司 监管处罚 警示函 2026",
    "福建上市公司 退市风险 ST 2026",
    "福建上市公司 股权激励 回购 2026",
    "福建上市公司 重大合同 资产重组 2026",
]

# ── LLM 筛选 Prompt ───────────────────────────────────────────────────────────
FILTER_PROMPT = """你是一名福建证券公司分公司负责人的资讯助理。
你的任务是从以下搜索结果中，筛选出金融业内人士（券商、银行、基金、监管）会真正关注的资讯。

筛选标准：
- **时间要求**：只保留2026年的资讯，2025年及更早的一律剔除
- 保留：政策文件、监管处罚/警示、战略合作、业务落地、签约、股东变动、高管变更、债券发行、重要公告
- 剔除：投教活动、公益活动、安全宣传、普通招聘广告、无实质内容的泛泛报道、2025年及更早的旧闻

对每条保留的资讯，输出标准格式（JSON数组）：
[
  {{
    "source": "来源机构，如【福建证监局】",
    "title": "一句话标题，含核心事件，不超过50字",
    "summary": "2-3句话摘要，说清楚是什么、涉及谁、主要数字或结论",
    "url": "原始链接",
    "date": "日期，格式MM月DD日",
    "year": "年份，必须是2026"
  }}
]

如果没有符合标准的内容，返回空数组 []。
只输出 JSON，不要任何其他解释文字。

以下是搜索结果：
{results}
"""

# ── Tavily 搜索 ───────────────────────────────────────────────────────────────
def tavily_search(query: str, days: int = 7) -> list:
    """调用 Tavily 搜索，返回结果列表"""
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": 8,
                "days": days,
                "include_answer": False,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("results", [])
        logger.warning(f"Tavily 返回 {resp.status_code}: {query}")
        return []
    except Exception as e:
        logger.error(f"Tavily 搜索失败: {e}")
        return []


# ── 同花顺公告搜索 ─────────────────────────────────────────────────────────────
def iwencai_search(query: str) -> list:
    """调用同花顺问财 announcement-search API"""
    if not IWENCAI_KEY:
        logger.warning("IWENCAI_API_KEY 未配置，跳过同花顺搜索")
        return []
    try:
        trace_id = secrets.token_hex(32)
        resp = requests.post(
            "https://openapi.iwencai.com/v1/comprehensive/search",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {IWENCAI_KEY}",
                "X-Claw-Call-Type": "normal",
                "X-Claw-Skill-Id": "announcement-search",
                "X-Claw-Skill-Version": "1.0.0",
                "X-Claw-Plugin-Id": "none",
                "X-Claw-Plugin-Version": "none",
                "X-Claw-Trace-Id": trace_id,
            },
            json={"channels": ["announcement"], "app_id": "AIME_SKILL", "query": query},
            timeout=20,
        )
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            return [
                {
                    "title": item.get("title", ""),
                    "content": item.get("summary", ""),
                    "url": item.get("url", ""),
                    "published_date": item.get("publish_date", ""),
                }
                for item in data
            ]
        return []
    except Exception as e:
        logger.error(f"同花顺搜索失败: {e}")
        return []


# ── LLM 筛选 ──────────────────────────────────────────────────────────────────
def llm_filter(raw_results: list, category: str) -> list:
    """用 OpenRouter 筛选和格式化资讯，分批处理避免 token 超限"""
    if not raw_results:
        return []

    BATCH_SIZE = 8  # 每批最多8条，避免输出 token 超限
    all_filtered = []

    for batch_idx in range(0, len(raw_results), BATCH_SIZE):
        batch = raw_results[batch_idx:batch_idx + BATCH_SIZE]
        # 截断每条摘要避免输入过长
        results_text = "\n\n".join(
            f"[{i}] 标题: {r.get('title','')[:100]}\n"
            f"摘要: {(r.get('content','') or r.get('snippet',''))[:300]}\n"
            f"链接: {r.get('url','')}\n"
            f"日期: {r.get('published_date','') or r.get('published','')}"
            for i, r in enumerate(batch)
        )

        try:
            for attempt in range(3):  # 最多重试3次
                try:
                    resp = requests.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {OPENROUTER_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": "qwen/qwen3-8b",
                            "messages": [
                                {
                                    "role": "user",
                                    "content": FILTER_PROMPT.format(results=results_text),
                                }
                            ],
                            "temperature": 0.1,
                            "max_tokens": 2000,
                        },
                        timeout=60,
                    )
                    if resp.status_code != 200:
                        logger.warning(f"OpenRouter {category} batch {batch_idx} 返回 {resp.status_code}: {resp.text[:200]}")
                        continue
                    break  # 成功，跳出重试
                except (requests.exceptions.Timeout, requests.exceptions.SSLError) as e:
                    if attempt < 2:
                        logger.warning(f"{category} batch {batch_idx} 网络错误，重试 {attempt+1}/3: {e}")
                        time.sleep(2)
                        continue
                    else:
                        raise  # 最后一次重试失败，抛出异常
            content = resp.json()["choices"][0]["message"]["content"].strip()
            content = content.replace("```json", "").replace("```", "").strip()
            start = content.find("[")
            end = content.rfind("]") + 1
            if start < 0 or end <= start:
                logger.warning(f"{category} batch {batch_idx} 未提取到 JSON 数组: {content[:200]}")
                continue
            try:
                items = json.loads(content[start:end])
                if isinstance(items, list):
                    # 过滤掉非字典元素
                    valid_items = [it for it in items if isinstance(it, dict)]
                    all_filtered.extend(valid_items)
            except json.JSONDecodeError as je:
                logger.warning(f"{category} batch {batch_idx} JSON 解析失败: {je}; content={content[:200]}")
                continue
        except Exception as e:
            logger.error(f"LLM 筛选异常 ({category} batch {batch_idx}): {e}")
            continue

        time.sleep(0.5)

    # 后处理：按年份过滤
    all_filtered = filter_by_year(all_filtered, 2026)

    return all_filtered


# ── 飞书 API 基础 ─────────────────────────────────────────────────────────────
def feishu_get_token() -> str:
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
        timeout=10,
    )
    return resp.json().get("tenant_access_token", "")


# ── 飞书文档创建 ──────────────────────────────────────────────────────────────
def _make_para(content: str, bold: bool = False) -> dict:
    style = {"bold": True} if bold else {}
    return {
        "block_type": 2,
        "text": {
            "elements": [{"text_run": {"content": content, "text_element_style": style}}],
            "style": {},
        },
    }


def _make_heading(content: str, level: int = 2) -> dict:
    block_type = 3 if level == 1 else 4
    key = "heading1" if level == 1 else "heading2"
    return {
        "block_type": block_type,
        key: {
            "elements": [{"text_run": {"content": content, "text_element_style": {}}}],
            "style": {},
        },
    }


def _sections_to_blocks(sections: dict) -> list:
    blocks = []
    section_order = ["政策法规/监管动态", "金融同业", "上市公司", "省市属企业"]
    roman = ["一", "二", "三", "四"]

    for i, name in enumerate(section_order):
        blocks.append(_make_heading(f"{roman[i]}、{name}", level=2))
        items = sections.get(name, [])
        if not items:
            blocks.append(_make_para("（本周暂无相关资讯）"))
            blocks.append(_make_para(""))
            continue
        for j, item in enumerate(items, 1):
            source = item.get("source", "")
            title = item.get("title", "")
            date = item.get("date", "")
            date_str = f"（{date}）" if date else ""
            blocks.append(_make_para(f"{j}. {source}{title}{date_str}", bold=True))
            if item.get("summary"):
                blocks.append(_make_para(item["summary"]))
            if item.get("url"):
                blocks.append(_make_para(item["url"]))
            blocks.append(_make_para(""))

    return blocks


def feishu_create_doc(title: str, sections: dict) -> str:
    """创建飞书 docx 文档，写入周报内容，返回文档 URL"""
    token = feishu_get_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 1. 创建空文档
    resp = requests.post(
        "https://open.feishu.cn/open-apis/docx/v1/documents",
        headers=headers,
        json={"title": title},
        timeout=15,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"创建文档失败: {data}")
    doc_id = data["data"]["document"]["document_id"]
    logger.info(f"文档已创建: {doc_id}")

    # 2. 批量插入内容块（飞书限制单次 ≤ 200 blocks）
    blocks = _sections_to_blocks(sections)
    for batch_start in range(0, len(blocks), 50):
        batch = blocks[batch_start: batch_start + 50]
        r = requests.post(
            f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
            headers=headers,
            json={"children": batch, "index": batch_start},
            timeout=20,
        )
        if r.json().get("code") != 0:
            logger.warning(f"插入块失败（batch {batch_start}）: {r.json()}")

    doc_url = f"https://www.feishu.cn/docx/{doc_id}"
    logger.info(f"文档写入完成: {doc_url}")
    return doc_url


def feishu_send_link(receive_id: str, receive_type: str, doc_url: str, title: str) -> bool:
    """把文档链接发回触发对话"""
    token = feishu_get_token()
    text = f"📋 {title}\n\n文档已生成：{doc_url}"
    resp = requests.post(
        f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_type}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}),
        },
        timeout=15,
    )
    result = resp.json()
    if result.get("code") == 0:
        logger.info("文档链接已推送")
        return True
    logger.error(f"推送链接失败: {result}")
    return False


def _doc_title() -> str:
    today = datetime.now()
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)
    return f"福建金融资讯周报（{last_monday.month}月{last_monday.day}日—{last_sunday.month}月{last_sunday.day}日）"


def dedup_results(items: list) -> list:
    """按 URL 去重"""
    seen = set()
    out = []
    for it in items:
        url = it.get("url", "")
        if url and url in seen:
            continue
        seen.add(url)
        out.append(it)
    return out


# ── 主流程 ────────────────────────────────────────────────────────────────────
def run(receive_id: str = None, receive_type: str = "open_id"):
    logger.info("开始抓取福建金融资讯周报")
    sections = {}

    # 1-2-4类：Tavily 搜索
    for category, queries in QUERIES.items():
        logger.info(f"抓取: {category}")
        raw = []
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(tavily_search, q): q for q in queries}
            for f in as_completed(futures):
                raw.extend(f.result())
        raw = dedup_results(raw)
        logger.info(f"  原始条目（去重后）: {len(raw)}")
        filtered = llm_filter(raw, category)
        logger.info(f"  筛选后: {len(filtered)}")
        sections[category] = filtered
        time.sleep(1)

    # 第3类：同花顺 + Tavily 结合
    logger.info("抓取: 上市公司")
    raw_listed = []
    for q in FUJIAN_LISTED_QUERIES:
        raw_listed.extend(iwencai_search(q))
        time.sleep(0.5)
    tavily_listed_queries = [
        "福建上市公司 公告 减持 增持 回购",
        "福建上市公司 高管变更 董事长 总经理",
        "福建上市公司 监管处罚 警示函 ST",
    ]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(tavily_search, q): q for q in tavily_listed_queries}
        for f in as_completed(futures):
            raw_listed.extend(f.result())
    raw_listed = dedup_results(raw_listed)
    logger.info(f"  上市公司原始条目（去重后）: {len(raw_listed)}")
    filtered_listed = llm_filter(raw_listed, "上市公司")
    logger.info(f"  上市公司筛选后: {len(filtered_listed)}")
    sections["上市公司"] = filtered_listed

    # 创建飞书文档
    title = _doc_title()
    doc_url = feishu_create_doc(title, sections)
    logger.info(f"周报文档: {doc_url}")

    # 发链接回给触发者
    if receive_id:
        feishu_send_link(receive_id, receive_type, doc_url, title)
    else:
        feishu_send_link(FEISHU_DEFAULT_CHAT_ID, "chat_id", doc_url, title)

    logger.info("周报完成")
    return doc_url


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--receive-id", default=None, help="飞书 open_id 或 chat_id")
    parser.add_argument("--receive-type", default="open_id", choices=["open_id", "chat_id"])
    args = parser.parse_args()
    run(receive_id=args.receive_id, receive_type=args.receive_type)

"""
视频字幕/内容提取模块
支持 YouTube（通过Supadata API）和 B站（直接API）

独立CLI脚本，无内部依赖
用法: python3 video_data.py --url "https://youtube.com/watch?v=xxx"
"""

import re
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=2)

SUPADATA_API_KEY = os.getenv("SUPADATA_API_KEY", "")


def _extract_youtube_id(url: str) -> str | None:
    """从URL提取YouTube视频ID"""
    patterns = [
        r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:embed/)([a-zA-Z0-9_-]{11})',
        r'(?:shorts/)([a-zA-Z0-9_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def _extract_bilibili_id(url: str) -> str | None:
    """从URL提取B站BV号"""
    m = re.search(r'(BV[a-zA-Z0-9]+)', url)
    return m.group(1) if m else None


def _fetch_youtube_transcript(video_id: str) -> dict:
    """通过Supadata REST API获取YouTube字幕"""
    if not SUPADATA_API_KEY:
        return {"success": False, "error": "Supadata API Key未配置（设置环境变量 SUPADATA_API_KEY）", "content": ""}

    import httpx

    url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {"x-api-key": SUPADATA_API_KEY}

    # 尝试多种语言
    for lang in ["zh-Hans", "zh", "en", None]:
        try:
            params = {"url": url, "text": "true"}
            if lang:
                params["lang"] = lang
            resp = httpx.get(
                "https://api.supadata.ai/v1/youtube/transcript",
                params=params, headers=headers, timeout=30
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("content", "")
                if content and len(content) > 50:
                    return {
                        "success": True,
                        "content": content,
                        "lang": data.get("lang", lang or "auto"),
                        "source": "supadata",
                    }
        except Exception:
            continue

    return {"success": False, "error": "该视频无可用字幕", "content": ""}


def _fetch_youtube_transcript_fallback(video_id: str) -> dict:
    """备用方案：通过免费第三方API获取字幕"""
    import httpx

    # 方案1: noembed获取视频标题和描述
    try:
        resp = httpx.get(
            f"https://noembed.com/embed?url=https://www.youtube.com/watch?v={video_id}",
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            title = data.get("title", "")
            author = data.get("author_name", "")
            if title:
                return {
                    "success": True,
                    "content": f"视频标题：{title}\n作者：{author}\n(注：仅获取到标题信息，未获取到完整字幕)",
                    "lang": "metadata",
                    "source": "noembed",
                    "partial": True,
                    "title": title,
                    "author": author,
                }
    except Exception:
        pass

    return {"success": False, "error": "所有方案均失败", "content": ""}


def _fetch_bilibili_transcript(bvid: str) -> dict:
    """获取B站视频字幕"""
    import httpx

    try:
        # 获取CID
        resp = httpx.get(
            f"https://api.bilibili.com/x/player/pagelist?bvid={bvid}",
            timeout=10
        )
        if resp.status_code != 200:
            return {"success": False, "error": "B站API请求失败", "content": ""}

        data = resp.json()
        if not data.get("data"):
            return {"success": False, "error": "未找到视频", "content": ""}

        cid = data["data"][0]["cid"]
        title = data["data"][0].get("part", "")

        # 获取视频信息
        info_resp = httpx.get(
            f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
            timeout=10
        )
        video_info = ""
        if info_resp.status_code == 200:
            info_data = info_resp.json().get("data", {})
            video_info = (
                f"标题：{info_data.get('title', '')}\n"
                f"UP主：{info_data.get('owner', {}).get('name', '')}\n"
                f"播放量：{info_data.get('stat', {}).get('view', '')}\n"
                f"简介：{info_data.get('desc', '')}\n"
            )

        # 尝试获取字幕
        sub_resp = httpx.get(
            f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}",
            timeout=10
        )
        if sub_resp.status_code == 200:
            sub_data = sub_resp.json()
            subtitles = sub_data.get("data", {}).get("subtitle", {}).get("subtitles", [])
            if subtitles:
                # 下载字幕内容
                sub_url = "https:" + subtitles[0]["subtitle_url"]
                sub_content_resp = httpx.get(sub_url, timeout=10)
                if sub_content_resp.status_code == 200:
                    sub_json = sub_content_resp.json()
                    texts = [item["content"] for item in sub_json.get("body", [])]
                    full_text = "\n".join(texts)
                    return {
                        "success": True,
                        "content": f"{video_info}\n字幕内容：\n{full_text}",
                        "lang": subtitles[0].get("lan", "zh"),
                        "source": "bilibili_subtitle",
                    }

        # 没有字幕，返回视频信息
        if video_info:
            return {
                "success": True,
                "content": video_info + "\n(该视频无CC字幕，以上为视频公开信息)",
                "lang": "metadata",
                "source": "bilibili_info",
                "partial": True,
            }

        return {"success": False, "error": "未获取到B站视频信息", "content": ""}
    except Exception as e:
        return {"success": False, "error": str(e), "content": ""}


async def get_video_content(url: str) -> dict:
    """
    从视频URL获取文字内容。
    返回 {"success": bool, "content": str, "source": str, "title": str}
    """
    loop = asyncio.get_event_loop()

    # 判断平台
    yt_id = _extract_youtube_id(url)
    bili_id = _extract_bilibili_id(url)

    if yt_id:
        # YouTube: Supadata → fallback(noembed)
        result = await loop.run_in_executor(_executor, _fetch_youtube_transcript, yt_id)
        if not result["success"] or not result.get("content"):
            result = await loop.run_in_executor(_executor, _fetch_youtube_transcript_fallback, yt_id)
        return result

    elif bili_id:
        # B站
        result = await loop.run_in_executor(_executor, _fetch_bilibili_transcript, bili_id)
        return result

    else:
        # 其他URL: 不支持
        return {
            "success": False,
            "error": "unsupported_platform",
            "content": "",
        }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="提取视频字幕/内容（支持YouTube和B站）")
    parser.add_argument("--url", type=str, required=True, help="视频URL（YouTube或B站）")
    args = parser.parse_args()

    print(f"正在提取视频内容：{args.url} ...", flush=True)

    result = asyncio.run(get_video_content(args.url))

    if result.get("success"):
        print(f"\n来源：{result.get('source', 'unknown')}")
        print(f"语言：{result.get('lang', 'unknown')}")
        print(f"{'=' * 60}")
        print(result.get("content", ""))
    else:
        print(f"\n提取失败：{result.get('error', '未知错误')}")

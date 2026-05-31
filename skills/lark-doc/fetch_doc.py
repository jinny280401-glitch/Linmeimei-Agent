#!/usr/bin/env python3
"""Fetch Lark/Feishu document and convert to Markdown using REST API."""

import json
import os
import re
import sys
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

LARK_APP_ID = os.getenv("LARK_APP_ID", "")
LARK_APP_SECRET = os.getenv("LARK_APP_SECRET", "")
LARK_DOC_URL = os.getenv("LARK_DOC_URL", "")
LARK_DOMAIN = os.getenv("LARK_DOMAIN", "https://open.feishu.cn")


def extract_document_id(url: str) -> str | None:
    """Extract document ID from Lark document URL."""
    patterns = [
        r"/wiki/([a-zA-Z0-9]+)",
        r"/docx/([a-zA-Z0-9]+)",
        r"/docs/([a-zA-Z0-9]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    """Get tenant access token using app credentials."""
    url = urljoin(LARK_DOMAIN, "/open-apis/auth/v3/tenant_access_token/internal")
    payload = {"app_id": app_id, "app_secret": app_secret}
    headers = {"Content-Type": "application/json"}
    
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    
    if data.get("code") != 0:
        raise Exception(f"Failed to get access token: {data}")
    
    return data["tenant_access_token"]


def fetch_document_blocks(token: str, document_id: str) -> list[dict]:
    """Fetch all blocks from a Lark document using REST API."""
    all_blocks = []
    page_token = ""
    
    base_url = urljoin(LARK_DOMAIN, f"/open-apis/docx/v1/documents/{document_id}/blocks")
    
    while True:
        params = {"page_size": 500, "document_revision_id": -1}
        if page_token:
            params["page_token"] = page_token
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(base_url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") != 0:
            raise Exception(f"Failed to fetch blocks: {data}")
        
        items = data.get("data", {}).get("items", [])
        all_blocks.extend(items)
        
        page_token = data.get("data", {}).get("page_token", "")
        has_more = data.get("data", {}).get("has_more", False)
        
        if not has_more or not page_token:
            break
    
    return all_blocks


def extract_text_from_elements(elements: list[dict]) -> str:
    """Extract text content from text elements."""
    if not elements:
        return ""
    text_parts = []
    for element in elements:
        if "text_run" in element:
            content = element["text_run"].get("content", "")
            text_parts.append(content)
        elif "mention_user" in element:
            text_parts.append("@user")
        elif "mention_doc" in element:
            title = element["mention_doc"].get("title", "document")
            text_parts.append(f"[{title}]")
        elif "equation" in element:
            content = element["equation"].get("content", "")
            text_parts.append(f"${content}$")
    return "".join(text_parts)


def block_to_markdown(block: dict, blocks_map: dict) -> str:
    """Convert a single block to Markdown."""
    block_type = block.get("block_type")
    
    if block_type == "page":
        return ""
    
    elif block_type == "text":
        text_block = block.get("text", {})
        elements = text_block.get("elements", [])
        return extract_text_from_elements(elements)
    
    elif block_type in ["heading1", "heading2", "heading3", "heading4", 
                         "heading5", "heading6", "heading7", "heading8", "heading9"]:
        level = int(block_type.replace("heading", ""))
        heading_block = block.get(block_type, {})
        elements = heading_block.get("elements", [])
        text = extract_text_from_elements(elements)
        return f"{'#' * level} {text}"
    
    elif block_type == "bullet":
        bullet_block = block.get("bullet", {})
        elements = bullet_block.get("elements", [])
        text = extract_text_from_elements(elements)
        return f"- {text}"
    
    elif block_type == "ordered":
        ordered_block = block.get("ordered", {})
        elements = ordered_block.get("elements", [])
        text = extract_text_from_elements(elements)
        return f"1. {text}"
    
    elif block_type == "code":
        code_block = block.get("code", {})
        elements = code_block.get("elements", [])
        text = extract_text_from_elements(elements)
        lang = code_block.get("language", "")
        return f"```{lang}\n{text}\n```"
    
    elif block_type == "quote":
        quote_block = block.get("quote", {})
        elements = quote_block.get("elements", [])
        text = extract_text_from_elements(elements)
        return f"> {text}"
    
    elif block_type == "todo":
        todo_block = block.get("todo", {})
        elements = todo_block.get("elements", [])
        text = extract_text_from_elements(elements)
        done = todo_block.get("style", {}).get("done", False)
        checkbox = "[x]" if done else "[ ]"
        return f"- {checkbox} {text}"
    
    elif block_type == "divider":
        return "---"
    
    elif block_type == "table":
        return "[Table]"
    
    elif block_type == "grid":
        return ""  # Skip grid containers
    
    elif block_type == "grid_column":
        return ""  # Skip grid columns
    
    else:
        return ""


def blocks_to_markdown(blocks: list[dict]) -> str:
    """Convert all blocks to Markdown document."""
    blocks_map = {block.get("block_id"): block for block in blocks}
    
    # Build parent-child relationships
    children_map: dict[str, list[str]] = {}
    root_blocks: list[str] = []
    
    for block in blocks:
        block_id = block.get("block_id")
        parent_id = block.get("parent_id")
        
        if parent_id:
            if parent_id not in children_map:
                children_map[parent_id] = []
            if block_id not in children_map[parent_id]:
                children_map[parent_id].append(block_id)
        else:
            root_blocks.append(block_id)
    
    markdown_lines = []
    
    def process_block(block_id: str, indent_level: int = 0):
        if block_id not in blocks_map:
            return
        
        block = blocks_map[block_id]
        md = block_to_markdown(block, blocks_map)
        
        if md:
            if indent_level > 0 and block.get("block_type") in ["bullet", "ordered", "todo"]:
                md = "  " * indent_level + md
            markdown_lines.append(md)
        
        # Process children
        children = children_map.get(block_id, [])
        for child_id in children:
            next_indent = indent_level + 1 if block.get("block_type") in ["bullet", "ordered", "todo"] else 0
            process_block(child_id, next_indent)
    
    for block_id in root_blocks:
        process_block(block_id)
    
    return "\n\n".join(markdown_lines)


def fetch_lark_document() -> dict:
    """Main function to fetch and convert Lark document."""
    if not LARK_APP_ID or not LARK_APP_SECRET:
        return {
            "success": False,
            "error": "LARK_APP_ID or LARK_APP_SECRET not configured",
        }
    
    if not LARK_DOC_URL:
        return {
            "success": False,
            "error": "LARK_DOC_URL not configured",
        }
    
    document_id = extract_document_id(LARK_DOC_URL)
    if not document_id:
        return {
            "success": False,
            "error": f"Cannot extract document ID from URL: {LARK_DOC_URL}",
        }
    
    try:
        # Get access token
        token = get_tenant_access_token(LARK_APP_ID, LARK_APP_SECRET)
        
        # Fetch document blocks
        blocks = fetch_document_blocks(token, document_id)
        
        if not blocks:
            return {
                "success": False,
                "error": "Document is empty",
            }
        
        # Convert to Markdown
        markdown_content = blocks_to_markdown(blocks)
        
        return {
            "success": True,
            "documentId": document_id,
            "url": LARK_DOC_URL,
            "content": markdown_content,
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def main():
    result = fetch_lark_document()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Append troubleshooting summary to Lark/Feishu document using REST API."""

import argparse
import json
import os
import re
import sys
from datetime import datetime
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


def append_blocks_to_document(token: str, document_id: str, blocks: list[dict]) -> dict:
    """Append blocks to a Lark document using REST API."""
    url = urljoin(LARK_DOMAIN, f"/open-apis/docx/v1/documents/{document_id}/blocks")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "children": blocks,
        "index": -1,  # Append at the end
        "document_revision_id": -1
    }
    
    params = {"block_id": document_id}  # Append to root
    
    response = requests.post(url, params=params, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    
    return data


def create_text_block(content: str, bold: bool = False) -> dict:
    """Create a text block with the given content."""
    return {
        "block_type": "text",
        "text": {
            "elements": [
                {
                    "text_run": {
                        "content": content,
                        "text_element_style": {
                            "bold": bold
                        }
                    }
                }
            ]
        }
    }


def create_heading_block(content: str, level: int = 3) -> dict:
    """Create a heading block (level 1-9)."""
    heading_type = f"heading{level}"
    return {
        "block_type": heading_type,
        heading_type: {
            "elements": [
                {
                    "text_run": {
                        "content": content
                    }
                }
            ]
        }
    }


def create_bullet_block(content: str) -> dict:
    """Create a bullet list item block."""
    return {
        "block_type": "bullet",
        "bullet": {
            "elements": [
                {
                    "text_run": {
                        "content": content
                    }
                }
            ]
        }
    }


def create_divider_block() -> dict:
    """Create a divider block."""
    return {
        "block_type": "divider",
        "divider": {}
    }


def append_troubleshooting_summary(
    title: str,
    problem: str,
    steps: list[str],
    solution: str,
    notes: str | None = None,
) -> dict:
    """
    Append a troubleshooting summary to the Lark document.

    Args:
        title: Title of the troubleshooting case
        problem: Description of the problem
        steps: List of troubleshooting steps taken
        solution: The solution that resolved the issue
        notes: Optional additional notes

    Returns:
        dict with success status and message
    """
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

        # Build blocks for the summary
        blocks = []

        # Add divider first
        blocks.append(create_divider_block())

        # Add title with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        blocks.append(create_heading_block(f"{title} ({timestamp})", level=3))

        # Add problem description
        blocks.append(create_heading_block("问题描述", level=4))
        blocks.append(create_text_block(problem))

        # Add troubleshooting steps
        blocks.append(create_heading_block("排查步骤", level=4))
        for step in steps:
            blocks.append(create_bullet_block(step))

        # Add solution
        blocks.append(create_heading_block("解决方案", level=4))
        blocks.append(create_text_block(solution))

        # Add notes if provided
        if notes:
            blocks.append(create_heading_block("备注", level=4))
            blocks.append(create_text_block(notes))

        # Append blocks to document
        result = append_blocks_to_document(token, document_id, blocks)

        if result.get("code") != 0:
            return {
                "success": False,
                "error": f"Failed to append summary: {result}",
            }

        return {
            "success": True,
            "documentId": document_id,
            "url": LARK_DOC_URL,
            "message": f"Successfully appended troubleshooting summary: {title}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser(
        description="Append troubleshooting summary to Lark document"
    )
    parser.add_argument(
        "-t", "--title",
        required=True,
        help="Title of the troubleshooting case"
    )
    parser.add_argument(
        "-p", "--problem",
        required=True,
        help="Description of the problem"
    )
    parser.add_argument(
        "-s", "--steps",
        required=True,
        help="JSON array of troubleshooting steps"
    )
    parser.add_argument(
        "-o", "--solution",
        required=True,
        help="The solution that resolved the issue"
    )
    parser.add_argument(
        "-n", "--notes",
        help="Optional additional notes"
    )

    args = parser.parse_args()

    try:
        steps = json.loads(args.steps)
        if not isinstance(steps, list):
            raise ValueError("Steps must be a JSON array")
    except json.JSONDecodeError as e:
        print(json.dumps({
            "success": False,
            "error": f"Invalid JSON for steps: {e}"
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    result = append_troubleshooting_summary(
        title=args.title,
        problem=args.problem,
        steps=steps,
        solution=args.solution,
        notes=args.notes,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()

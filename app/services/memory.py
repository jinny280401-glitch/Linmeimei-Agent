"""用户记忆管理 — 每用户独立 SQLite"""

import os
import sqlite3
import logging
from datetime import datetime
from app.config import settings
from app.models.schemas import UserProfile

logger = logging.getLogger(__name__)

# 建表 SQL
_INIT_SQL = """
CREATE TABLE IF NOT EXISTS user_profile (
    user_id TEXT PRIMARY KEY,
    user_name TEXT DEFAULT '',
    gender TEXT DEFAULT '',
    call_name TEXT DEFAULT '',
    first_seen TEXT DEFAULT '',
    last_seen TEXT DEFAULT '',
    interests TEXT DEFAULT '',
    notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    skill_used TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS key_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_type TEXT NOT NULL,
    fact_key TEXT NOT NULL,
    fact_value TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS client_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_name TEXT NOT NULL,
    client_info TEXT NOT NULL,
    priority_score REAL DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);
"""


def _get_db_path(user_id: str) -> str:
    """获取用户数据库路径"""
    os.makedirs(settings.users_db_dir, exist_ok=True)
    return os.path.join(settings.users_db_dir, f"{user_id}.db")


def _get_conn(user_id: str) -> sqlite3.Connection:
    """获取数据库连接，首次访问自动建表"""
    db_path = _get_db_path(user_id)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_INIT_SQL)
    return conn


def get_user_profile(user_id: str) -> UserProfile | None:
    """读取用户画像，不存在返回 None"""
    conn = _get_conn(user_id)
    try:
        row = conn.execute(
            "SELECT * FROM user_profile WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row:
            return UserProfile(**dict(row))
        return None
    finally:
        conn.close()


def save_user_profile(profile: UserProfile) -> None:
    """保存或更新用户画像"""
    conn = _get_conn(profile.user_id)
    try:
        conn.execute("""
            INSERT INTO user_profile (user_id, user_name, gender, call_name, first_seen, last_seen, interests, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                user_name = excluded.user_name,
                gender = excluded.gender,
                call_name = excluded.call_name,
                last_seen = excluded.last_seen,
                interests = excluded.interests,
                notes = excluded.notes
        """, (
            profile.user_id, profile.user_name, profile.gender,
            profile.call_name, profile.first_seen, profile.last_seen,
            profile.interests, profile.notes,
        ))
        conn.commit()
    finally:
        conn.close()


def is_new_user(user_id: str) -> bool:
    """检查是否是新用户"""
    return get_user_profile(user_id) is None


def save_message(user_id: str, role: str, content: str, skill_used: str = "") -> None:
    """保存一条对话记录"""
    conn = _get_conn(user_id)
    try:
        conn.execute(
            "INSERT INTO conversations (role, content, skill_used) VALUES (?, ?, ?)",
            (role, content, skill_used),
        )
        # 只保留最近 100 轮（200 条消息）
        conn.execute("""
            DELETE FROM conversations WHERE id NOT IN (
                SELECT id FROM conversations ORDER BY id DESC LIMIT 200
            )
        """)
        conn.commit()
    finally:
        conn.close()


def get_recent_messages(user_id: str, limit: int = 20) -> list[dict]:
    """获取最近的对话记录"""
    conn = _get_conn(user_id)
    try:
        rows = conn.execute(
            "SELECT role, content, skill_used, created_at FROM conversations ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in reversed(rows)]
    finally:
        conn.close()


def save_key_fact(user_id: str, fact_type: str, fact_key: str, fact_value: str) -> None:
    """保存用户关键信息"""
    conn = _get_conn(user_id)
    try:
        conn.execute("""
            INSERT INTO key_facts (fact_type, fact_key, fact_value, updated_at)
            VALUES (?, ?, ?, datetime('now', 'localtime'))
        """, (fact_type, fact_key, fact_value))
        conn.commit()
    finally:
        conn.close()


def get_user_context(user_id: str) -> str:
    """生成用户上下文摘要，注入给 Claude"""
    profile = get_user_profile(user_id)
    messages = get_recent_messages(user_id, limit=10)

    parts = []

    if profile:
        parts.append(f"用户信息：{profile.user_name}")
        if profile.gender:
            gender_label = "男" if profile.gender == "male" else "女"
            parts.append(f"性别：{gender_label}，称呼：{profile.call_name}")
        else:
            parts.append("性别：未确认，请用「你」称呼")
        if profile.interests:
            parts.append(f"关注领域：{profile.interests}")
    else:
        parts.append("新用户，首次交互，需要自我介绍并询问性别")

    if messages:
        parts.append("\n最近对话：")
        for msg in messages[-6:]:
            role_label = "用户" if msg["role"] == "user" else "嘉勤"
            parts.append(f"  {role_label}：{msg['content'][:100]}")

    return "\n".join(parts)

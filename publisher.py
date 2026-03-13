#!/usr/bin/env python3
"""
Mann Made Socializer - Central Publisher
Routes posts through Postiz (primary) with agent-browser as fallback.
All post attempts are logged to data/post_log.db (SQLite).
"""
import os, json, sqlite3, time, asyncio
from pathlib import Path
from datetime import datetime
from enum import Enum

BASE = Path(__file__).parent


class PostStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"       # handed to Postiz
    POSTED = "posted"       # confirmed live
    FAILED = "failed"       # all attempts failed
    RETRYING = "retrying"   # in retry queue


def get_db() -> sqlite3.Connection:
    db_path = BASE / "data" / "post_log.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE IF NOT EXISTS post_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            content TEXT NOT NULL,
            media_path TEXT,
            scheduled_at TEXT,
            status TEXT DEFAULT 'pending',
            postiz_id TEXT,
            error TEXT,
            attempt_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            posted_at TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS retry_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_log_id INTEGER REFERENCES post_log(id),
            retry_at TEXT NOT NULL,
            reason TEXT
        )
    """)
    db.commit()
    return db


async def publish(
    client_id: str,
    platform: str,
    content: str,
    media_path: str = "",
    scheduled_at: str = "",
    api_key: str = ""
) -> dict:
    """
    Publish a post. Tries Postiz first, logs result.
    Returns {ok, post_id, status, log_id}
    """
    db = get_db()

    # Log the attempt
    cur = db.execute(
        "INSERT INTO post_log (client_id, platform, content, media_path, scheduled_at, status) VALUES (?,?,?,?,?,?)",
        (client_id, platform, content, media_path, scheduled_at, PostStatus.PENDING)
    )
    log_id = cur.lastrowid
    db.commit()

    # Try Postiz
    try:
        import httpx
        POSTIZ_URL = os.environ.get("POSTIZ_URL", "http://localhost:5001")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        payload = {
            "content": content,
            "integrations": [platform],
        }
        if scheduled_at:
            payload["scheduleDate"] = scheduled_at

        # Upload media if present
        if media_path and Path(media_path).exists():
            async with httpx.AsyncClient(timeout=60) as client:
                with open(media_path, "rb") as f:
                    upload = await client.post(
                        f"{POSTIZ_URL}/api/upload",
                        headers={"Authorization": f"Bearer {api_key}"},
                        files={"file": (Path(media_path).name, f)}
                    )
                    if upload.status_code == 200:
                        media_id = upload.json().get("id")
                        if media_id:
                            payload["media"] = [{"id": media_id}]

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{POSTIZ_URL}/api/posts", headers=headers, json=payload)

        if resp.status_code < 300:
            postiz_id = resp.json().get("id", "")
            db.execute(
                "UPDATE post_log SET status=?, postiz_id=?, updated_at=datetime('now') WHERE id=?",
                (PostStatus.QUEUED, postiz_id, log_id)
            )
            db.commit()
            return {"ok": True, "post_id": postiz_id, "status": PostStatus.QUEUED, "log_id": log_id}
        else:
            error = f"Postiz {resp.status_code}: {resp.text[:200]}"
            raise Exception(error)

    except Exception as e:
        error_msg = str(e)
        # Schedule for retry in 30 minutes
        retry_at = datetime.fromtimestamp(time.time() + 1800).isoformat()
        db.execute(
            "UPDATE post_log SET status=?, error=?, attempt_count=attempt_count+1, updated_at=datetime('now') WHERE id=?",
            (PostStatus.RETRYING, error_msg, log_id)
        )
        db.execute(
            "INSERT INTO retry_queue (post_log_id, retry_at, reason) VALUES (?,?,?)",
            (log_id, retry_at, error_msg)
        )
        db.commit()
        return {"ok": False, "error": error_msg, "status": PostStatus.RETRYING, "log_id": log_id}


def get_failed_posts(client_id: str = "") -> list:
    db = get_db()
    if client_id:
        rows = db.execute(
            "SELECT * FROM post_log WHERE client_id=? AND status IN ('failed','retrying') ORDER BY created_at DESC LIMIT 50",
            (client_id,)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM post_log WHERE status IN ('failed','retrying') ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
    return [dict(r) for r in rows]


def get_post_log(client_id: str = "", limit: int = 100) -> list:
    db = get_db()
    if client_id:
        rows = db.execute(
            "SELECT * FROM post_log WHERE client_id=? ORDER BY created_at DESC LIMIT ?",
            (client_id, limit)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM post_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]

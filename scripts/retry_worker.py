#!/usr/bin/env python3
"""
Retry Worker - processes the retry_queue table.
Run every 5 minutes via cron. Retries failed posts when connectivity is restored.
Also handles load-shedding: if Postiz is down, skip and retry later.
"""
import os, sys, sqlite3, asyncio, time
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))

from publisher import get_db, publish, PostStatus

POSTIZ_URL = os.environ.get("POSTIZ_URL", "http://localhost:5001")
MAX_ATTEMPTS = 5


def check_connectivity() -> bool:
    """Check if Postiz is reachable."""
    try:
        import urllib.request
        urllib.request.urlopen(f"{POSTIZ_URL}/api/status", timeout=5)
        return True
    except Exception:
        return False


async def process_retries():
    if not check_connectivity():
        print(f"[{datetime.now()}] Postiz unreachable - skipping retry run (load shedding?)")
        return

    db = get_db()
    now = datetime.now().isoformat()

    due = db.execute(
        "SELECT rq.id as rq_id, rq.post_log_id, pl.* "
        "FROM retry_queue rq "
        "JOIN post_log pl ON pl.id = rq.post_log_id "
        "WHERE rq.retry_at <= ? "
        "ORDER BY rq.retry_at LIMIT 10",
        (now,)
    ).fetchall()

    print(f"[{datetime.now()}] Found {len(due)} posts due for retry")

    for row in due:
        row = dict(row)
        if row.get("attempt_count", 0) >= MAX_ATTEMPTS:
            db.execute(
                "UPDATE post_log SET status=? WHERE id=?",
                (PostStatus.FAILED, row["post_log_id"])
            )
            db.execute("DELETE FROM retry_queue WHERE id=?", (row["rq_id"],))
            db.commit()
            print(f"  Post {row['post_log_id']} failed permanently after {MAX_ATTEMPTS} attempts")
            continue

        api_key = os.environ.get("POSTIZ_API_KEY", "")
        result = await publish(
            client_id=row["client_id"],
            platform=row["platform"],
            content=row["content"],
            media_path=row.get("media_path", ""),
            scheduled_at=row.get("scheduled_at", ""),
            api_key=api_key
        )

        if result["ok"]:
            db.execute("DELETE FROM retry_queue WHERE id=?", (row["rq_id"],))
            db.commit()
            print(f"  Post {row['post_log_id']} retried successfully")
        else:
            # Push retry time back by 30 more minutes
            next_retry = datetime.fromtimestamp(time.time() + 1800).isoformat()
            db.execute(
                "UPDATE retry_queue SET retry_at=? WHERE id=?",
                (next_retry, row["rq_id"])
            )
            db.commit()
            print(f"  Post {row['post_log_id']} retry failed again, next attempt: {next_retry}")


if __name__ == "__main__":
    asyncio.run(process_retries())

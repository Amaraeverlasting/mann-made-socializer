#!/usr/bin/env python3
"""Mann Made Media - Analytics Scraper"""
import json
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path.home() / ".openclaw/workspace"
TRACKER = BASE / "data/posted_tracker.json"
QUEUE = BASE / "skills/social-scheduler/queue.json"
SNAPSHOTS = Path(__file__).parent / "analytics/snapshots.json"
ENGAGEMENT = Path(__file__).parent / "analytics/engagement.json"

def load_json(path, default):
    try:
        return json.loads(path.read_text()) if path.exists() else default
    except:
        return default

def run():
    tracker_raw = load_json(TRACKER, [])
    # Handle both list format and dict format {"posts": [...]}
    if isinstance(tracker_raw, dict):
        posts = tracker_raw.get("posts", [])
    else:
        posts = tracker_raw

    queue = load_json(QUEUE, [])

    now = datetime.now()
    today = now.date().isoformat()
    week_ago = (now - timedelta(days=7)).isoformat()

    by_platform = {}
    posts_today = 0
    posts_week = 0

    for p in posts:
        platform = p.get("platform", "unknown")
        by_platform[platform] = by_platform.get(platform, 0) + 1
        ts = p.get("posted_at") or p.get("timestamp") or p.get("created_at") or ""
        if ts.startswith(today):
            posts_today += 1
        if ts >= week_ago:
            posts_week += 1

    by_status = {}
    for p in queue:
        s = p.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1

    top_posts = []
    for p in posts[-5:]:
        top_posts.append({
            "platform": p.get("platform", "?"),
            "content": (p.get("text") or p.get("content") or "")[:100],
            "date": (p.get("posted_at") or p.get("timestamp") or p.get("created_at") or "")[:10]
        })

    snapshot = {
        "date": today,
        "timestamp": now.isoformat(),
        "posts_total": len(posts),
        "posts_today": posts_today,
        "posts_this_week": posts_week,
        "by_platform": by_platform,
        "by_status": by_status,
        "queue_total": len(queue),
        "top_posts": top_posts
    }

    snapshots = load_json(SNAPSHOTS, [])
    # Remove today's snapshot if exists (replace)
    snapshots = [s for s in snapshots if s.get("date") != today]
    snapshots.append(snapshot)
    # Keep last 90 days
    snapshots = sorted(snapshots, key=lambda x: x.get("date", ""))[-90:]

    SNAPSHOTS.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOTS.write_text(json.dumps(snapshots, indent=2))
    print(f"Snapshot saved: {today} | {len(posts)} posts | {by_platform}")

if __name__ == "__main__":
    run()

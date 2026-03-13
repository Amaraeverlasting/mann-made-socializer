#!/usr/bin/env python3
"""
Video Scheduler - checks video_queue.json and posts due videos.
Run via cron every 15 minutes.
"""
import json, subprocess, sys, shutil
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
VIDEO_QUEUE = BASE / "video_queue.json"
ACCOUNTS_FILE = Path.home() / ".openclaw/workspace/skills/social-scheduler/accounts.json"
DONE_DIR = BASE / "videos/done"
FAILED_DIR = BASE / "videos/failed"

PLATFORM_SCRIPTS = {
    "x": BASE / "post_video_x.py",
    "tiktok": BASE / "post_video_tiktok.py",
    "instagram": BASE / "post_video_instagram.py",
    "youtube": BASE / "post_video_youtube.py",
}


def load_json(path, default):
    try:
        return json.loads(path.read_text()) if path.exists() else default
    except Exception:
        return default


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2))


def get_account(account_id):
    accounts = load_json(ACCOUNTS_FILE, {}).get("accounts", [])
    return next((a for a in accounts if a["id"] == account_id), None)


def run():
    queue = load_json(VIDEO_QUEUE, [])
    now = datetime.now()
    changed = False

    for item in queue:
        if item.get("status") not in ("scheduled", "pending"):
            continue

        # Check if due
        scheduled_at = item.get("scheduled_at")
        if scheduled_at:
            try:
                due = datetime.fromisoformat(scheduled_at)
                if due > now:
                    continue
            except Exception:
                pass

        video_path = item.get("file_path", "")
        if not Path(video_path).exists():
            print(f"Video file not found: {video_path}")
            item["status"] = "failed"
            changed = True
            continue

        caption = item.get("caption", "")
        account_ids = item.get("account_ids", [])

        for account_id in account_ids:
            if item.get("per_account_status", {}).get(account_id) == "posted":
                continue

            account = get_account(account_id)
            if not account or not account.get("active"):
                print(f"Account {account_id} not active, skipping")
                item["per_account_status"][account_id] = "skipped"
                continue

            platform = account.get("platform")
            script = PLATFORM_SCRIPTS.get(platform)

            if not script or not script.exists():
                print(f"No script for platform: {platform}")
                item["per_account_status"][account_id] = "failed"
                continue

            print(f"Posting {item['filename']} to {account_id} ({platform})...")
            result = subprocess.run(
                [sys.executable, str(script),
                 "--video", video_path,
                 "--caption", caption],
                capture_output=True, text=True, timeout=300
            )

            if result.returncode == 0:
                item["per_account_status"][account_id] = "posted"
                print(f"  OK: {account_id}")
            else:
                item["per_account_status"][account_id] = "failed"
                print(f"  FAILED: {account_id} - {result.stderr[:200]}")

        # Update overall status
        statuses = list(item.get("per_account_status", {}).values())
        if all(s == "posted" for s in statuses):
            item["status"] = "posted"
            item["posted_at"] = now.isoformat()
            DONE_DIR.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(video_path, DONE_DIR / Path(video_path).name)
            except Exception:
                pass
        elif all(s in ("failed", "skipped") for s in statuses):
            item["status"] = "failed"
            FAILED_DIR.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(video_path, FAILED_DIR / Path(video_path).name)
            except Exception:
                pass
        elif any(s == "posted" for s in statuses):
            item["status"] = "partial"

        changed = True

    if changed:
        save_json(VIDEO_QUEUE, queue)

    print(f"Done. Queue: {len(queue)} items.")


if __name__ == "__main__":
    run()

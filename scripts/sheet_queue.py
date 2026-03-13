#!/usr/bin/env python3
"""
Sheet Queue Poller - reads Google Sheet, downloads Drive videos, schedules via Postiz API.

Sheet columns (Row 1 = headers, data starts at Row 2):
  A: Client ID
  B: Platforms (comma-separated: x,linkedin,instagram,tiktok)
  C: Video Drive URL
  D: Caption - X
  E: Caption - LinkedIn
  F: Caption - Instagram
  G: Caption - TikTok
  H: Schedule Date (YYYY-MM-DD HH:MM or "now")
  I: Status (pending / downloading / queued / posted / error)
  J: Error message
  K: Postiz Post ID
  L: Posted At

Run: python3 sheet_queue.py --sheet-id SHEET_ID
Or set SHEET_ID env var.
"""
import os, sys, json, argparse, subprocess, time
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent.parent
POSTIZ_URL = os.environ.get("POSTIZ_URL", "http://localhost:5001")
GOG = "/opt/homebrew/bin/gog"


def _load_secrets() -> dict:
    """Load secrets from mann-made-media/secrets.json."""
    secrets_file = BASE / "secrets.json"
    if secrets_file.exists():
        try:
            return json.loads(secrets_file.read_text())
        except Exception:
            pass
    return {}


def gog_sheet_read(sheet_id: str) -> list:
    """Read all data rows from Google Sheet using gog CLI."""
    result = subprocess.run(
        [GOG, "sheets", "get", sheet_id, "A2:L1000",
         "--account", "mic@mannmade.co.za", "--json"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        print(f"Sheet read error: {result.stderr.strip()}")
        return []
    try:
        data = json.loads(result.stdout)
        # gog returns {"values": [[row1], [row2], ...]} or similar
        if isinstance(data, dict):
            return data.get("values", [])
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        print(f"Sheet parse error: {e}")
        return []


def gog_sheet_update(sheet_id: str, row_idx: int, col: str, value: str):
    """Update a single cell. row_idx is 0-based data row, so cell row = row_idx + 2."""
    cell = f"{col}{row_idx + 2}"
    subprocess.run(
        [GOG, "sheets", "update", sheet_id, cell,
         "--values-json", json.dumps([[value]]),
         "--account", "mic@mannmade.co.za"],
        capture_output=True, text=True, timeout=15
    )


def postiz_schedule(
    platform: str,
    caption: str,
    local_path: str,
    scheduled_at: str,
    api_key: str
) -> dict:
    """Schedule a post via Postiz API. Returns {ok, post_id, error}."""
    try:
        import httpx
    except ImportError:
        return {"ok": False, "error": "httpx not installed (pip3 install httpx)"}

    payload: dict = {
        "content": caption,
        "integrations": [platform],
    }
    if scheduled_at and scheduled_at.lower() != "now":
        payload["scheduleDate"] = scheduled_at

    try:
        with httpx.Client(timeout=30) as client:
            headers = {"Authorization": f"Bearer {api_key}"}

            # Upload media if video exists
            if local_path and Path(local_path).exists():
                with open(local_path, "rb") as f:
                    upload_resp = client.post(
                        f"{POSTIZ_URL}/api/upload",
                        headers=headers,
                        files={"file": (Path(local_path).name, f, "video/mp4")}
                    )
                    if upload_resp.status_code == 200:
                        media_id = upload_resp.json().get("id")
                        if media_id:
                            payload["media"] = [{"id": media_id}]

            resp = client.post(
                f"{POSTIZ_URL}/api/posts",
                headers={**headers, "Content-Type": "application/json"},
                json=payload
            )
            if resp.status_code < 300:
                return {"ok": True, "post_id": resp.json().get("id", "")}
            return {"ok": False, "error": resp.text[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def run_poll(sheet_id: str, api_key: str = "", dry_run: bool = False):
    """Read sheet, find pending rows, download videos, schedule via Postiz."""
    print(f"Polling sheet {sheet_id}...")
    rows = gog_sheet_read(sheet_id)
    if not rows:
        print("No rows found or sheet unreadable")
        return

    pending = [
        (i, r) for i, r in enumerate(rows)
        if len(r) > 8 and r[8].strip().lower() == "pending"
    ]
    print(f"Found {len(pending)} pending row(s)")

    for row_idx, row in pending:
        client_id = row[0].strip() if len(row) > 0 else ""
        platforms_raw = row[1].strip() if len(row) > 1 else ""
        drive_url = row[2].strip() if len(row) > 2 else ""
        captions = {
            "x":         row[3].strip() if len(row) > 3 else "",
            "linkedin":  row[4].strip() if len(row) > 4 else "",
            "instagram": row[5].strip() if len(row) > 5 else "",
            "tiktok":    row[6].strip() if len(row) > 6 else "",
        }
        schedule_date = row[7].strip() if len(row) > 7 else "now"
        platforms = [p.strip() for p in platforms_raw.split(",") if p.strip()]

        if not client_id or not platforms:
            print(f"Row {row_idx + 2}: skipping - missing client_id or platforms")
            continue

        print(f"\nRow {row_idx + 2}: {client_id} | {platforms} | {drive_url[:60]}")

        # Download video from Drive
        local_path = ""
        if drive_url:
            gog_sheet_update(sheet_id, row_idx, "I", "downloading")
            filename = f"post_{row_idx + 2}_{int(time.time())}.mp4"
            dl_result = subprocess.run(
                [
                    sys.executable,
                    str(BASE / "scripts/drive_sync.py"),
                    "--client", client_id,
                    "--url", drive_url,
                    "--filename", filename,
                ],
                capture_output=True, text=True, timeout=300
            )
            try:
                dl = json.loads(dl_result.stdout)
                if dl.get("ok"):
                    local_path = dl.get("local_path", "")
                    print(f"  Downloaded: {local_path}")
                else:
                    err = dl.get("error", "download failed")
                    print(f"  Download failed: {err}")
                    gog_sheet_update(sheet_id, row_idx, "I", "error")
                    gog_sheet_update(sheet_id, row_idx, "J", err[:200])
                    continue
            except Exception:
                print(f"  Drive sync parse error: {dl_result.stdout[:200]}")
                gog_sheet_update(sheet_id, row_idx, "I", "error")
                gog_sheet_update(sheet_id, row_idx, "J", "drive_sync parse error")
                continue

        if dry_run:
            print(f"  DRY RUN - would schedule to {platforms}")
            gog_sheet_update(sheet_id, row_idx, "I", "dry-run")
            continue

        # Schedule to each platform via Postiz
        gog_sheet_update(sheet_id, row_idx, "I", "queued")
        post_ids = []
        errors = []

        for platform in platforms:
            caption = captions.get(platform) or captions.get("x") or ""
            if not caption:
                errors.append(f"{platform}: no caption")
                continue
            result = postiz_schedule(platform, caption, local_path, schedule_date, api_key)
            if result["ok"]:
                post_ids.append(str(result.get("post_id", "")))
                print(f"  Scheduled to {platform}: {result.get('post_id')}")
            else:
                errors.append(f"{platform}: {result.get('error')}")
                print(f"  Failed {platform}: {result.get('error')}")

        if post_ids:
            gog_sheet_update(sheet_id, row_idx, "I", "queued")
            gog_sheet_update(sheet_id, row_idx, "K", ",".join(filter(None, post_ids)))
            gog_sheet_update(sheet_id, row_idx, "L", datetime.now().isoformat())
        else:
            gog_sheet_update(sheet_id, row_idx, "I", "error")
            gog_sheet_update(sheet_id, row_idx, "J", "; ".join(errors)[:200] or "No posts scheduled")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Poll Google Sheet and schedule posts via Postiz")
    parser.add_argument("--sheet-id", default=os.environ.get("SHEET_ID", ""))
    parser.add_argument("--api-key", default=os.environ.get("POSTIZ_API_KEY", ""))
    parser.add_argument("--dry-run", action="store_true", help="Read sheet and download videos but do not post")
    args = parser.parse_args()

    if not args.sheet_id:
        # Try secrets.json fallback
        secrets = _load_secrets()
        args.sheet_id = secrets.get("socializer", {}).get("sheetId", "")

    if not args.sheet_id:
        print("Error: --sheet-id required (or set SHEET_ID env var, or add socializer.sheetId to secrets.json)")
        sys.exit(1)

    if not args.api_key:
        secrets = _load_secrets()
        args.api_key = secrets.get("postiz", {}).get("apiKey", "")

    run_poll(args.sheet_id, args.api_key, args.dry_run)

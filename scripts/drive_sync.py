#!/usr/bin/env python3
"""
Drive Sync - Downloads videos from Google Drive to client inbox folders.
Uses gog CLI (already installed at /opt/homebrew/bin/gog) or direct download.
"""
import os, sys, json, argparse, subprocess, re
from pathlib import Path

BASE = Path(__file__).parent.parent
CLIENTS_DIR = BASE / "clients"

def get_file_id(drive_url: str) -> str:
    """Extract Google Drive file ID from URL."""
    patterns = [
        r'/file/d/([a-zA-Z0-9_-]+)',
        r'id=([a-zA-Z0-9_-]+)',
        r'/d/([a-zA-Z0-9_-]+)',
    ]
    for p in patterns:
        m = re.search(p, drive_url)
        if m:
            return m.group(1)
    return ""

def download_file(file_id: str, dest_path: Path) -> bool:
    """Download a file from Google Drive by file ID."""
    # Try gog CLI first
    try:
        result = subprocess.run(
            ["/opt/homebrew/bin/gog", "drive", "download", file_id, "--output", str(dest_path)],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0 and dest_path.exists():
            return True
    except Exception:
        pass

    # Fallback: direct download via urllib (for public/shared files)
    try:
        import urllib.request
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"
        urllib.request.urlretrieve(download_url, dest_path)
        if dest_path.exists() and dest_path.stat().st_size > 1000:
            return True
    except Exception as e:
        print(f"Download failed: {e}")
    return False

def sync_client(client_id: str, drive_url: str, filename: str) -> dict:
    """Download a Drive file to client inbox. Returns {ok, local_path, error}."""
    config_file = CLIENTS_DIR / f"{client_id}.json"
    if not config_file.exists():
        return {"ok": False, "error": f"Client {client_id} not found"}

    config = json.loads(config_file.read_text())
    inbox = Path(config.get(
        "content_folder",
        f"/Users/mannai/.openclaw/workspace/assets/clients/{client_id}/inbox/"
    ))
    inbox.mkdir(parents=True, exist_ok=True)

    file_id = get_file_id(drive_url)
    if not file_id:
        return {"ok": False, "error": "Could not extract file ID from URL"}

    dest = inbox / filename
    if dest.exists():
        return {"ok": True, "local_path": str(dest), "cached": True}

    success = download_file(file_id, dest)
    if success:
        return {"ok": True, "local_path": str(dest)}
    return {"ok": False, "error": "Download failed"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download a Google Drive file to client inbox")
    parser.add_argument("--client", required=True, help="Client ID (must match clients/<id>.json)")
    parser.add_argument("--url", required=True, help="Google Drive share URL")
    parser.add_argument("--filename", required=True, help="Destination filename")
    args = parser.parse_args()
    result = sync_client(args.client, args.url, args.filename)
    print(json.dumps(result, indent=2))

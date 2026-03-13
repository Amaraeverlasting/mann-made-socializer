#!/usr/bin/env python3
"""
check_login_status.py - Check platform login status for a client via CDP.

Usage:
  python3 check_login_status.py --client mic-mann
  python3 check_login_status.py --client mic-mann --dry-run
  python3 check_login_status.py --all
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent
CLIENTS_DIR = BASE / "clients"

PLATFORM_URLS = {
    "x": "https://x.com",
    "linkedin": "https://www.linkedin.com",
    "instagram": "https://www.instagram.com",
    "tiktok": "https://www.tiktok.com",
    "youtube": "https://www.youtube.com",
}

# Selectors that indicate a logged-in state per platform
LOGIN_INDICATORS = {
    "x": [
        '[data-testid="SideNav_NewTweet_Button"]',
        '[aria-label="Compose tweet"]',
        '[data-testid="primaryColumn"]',
    ],
    "linkedin": [
        '.global-nav__me',
        '[data-control-name="identity_welcome_message"]',
        '.feed-identity-module',
    ],
    "instagram": [
        'svg[aria-label="New post"]',
        '[aria-label="Home"]',
        '._aclv',
    ],
    "tiktok": [
        '[data-e2e="profile-icon"]',
        '.header-login-out',
    ],
    "youtube": [
        '#avatar-btn',
        'yt-icon-button#button.ytd-topbar-menu-button-renderer',
    ],
}


def load_client(client_id: str) -> dict:
    f = CLIENTS_DIR / f"{client_id}.json"
    if not f.exists():
        print(f"ERROR: Client '{client_id}' not found at {f}", file=sys.stderr)
        sys.exit(1)
    return json.loads(f.read_text())


def save_login_status(client_id: str, status: dict):
    status_dir = CLIENTS_DIR / client_id
    status_dir.mkdir(parents=True, exist_ok=True)
    status_file = status_dir / "login_status.json"
    status_file.write_text(json.dumps(status, indent=2))


def check_platform_via_cdp(platform: str, cdp_port: int, dry_run: bool = False) -> dict:
    """Check if a platform shows a logged-in state via CDP."""
    url = PLATFORM_URLS.get(platform, "")
    if not url:
        return {"logged_in": None, "error": "Unknown platform", "last_checked": datetime.now().isoformat()}

    if dry_run:
        print(f"  [dry-run] Would check {platform} ({url}) on CDP port {cdp_port}")
        return {
            "logged_in": None,
            "error": "dry-run",
            "last_checked": datetime.now().isoformat(),
            "url": url,
            "cdp_port": cdp_port,
        }

    try:
        import urllib.request
        import urllib.error

        # Get list of open tabs from CDP
        tabs_url = f"http://127.0.0.1:{cdp_port}/json"
        with urllib.request.urlopen(tabs_url, timeout=3) as resp:
            tabs = json.loads(resp.read())

        # Find or note platform tab
        platform_tab = None
        for tab in tabs:
            if platform.lower() in tab.get("url", "").lower():
                platform_tab = tab
                break

        if not platform_tab and tabs:
            # Use first available tab
            platform_tab = tabs[0]

        if not platform_tab:
            return {
                "logged_in": False,
                "error": "No tabs open in Chrome",
                "last_checked": datetime.now().isoformat(),
                "cdp_port": cdp_port,
            }

        # Use CDP Runtime.evaluate to check for login indicators
        ws_url = platform_tab.get("webSocketDebuggerUrl", "")
        if not ws_url:
            return {
                "logged_in": None,
                "error": "No WebSocket debugger URL",
                "last_checked": datetime.now().isoformat(),
            }

        # Navigate and check - requires websockets
        try:
            import websocket
            indicators = LOGIN_INDICATORS.get(platform, [])
            selector_js = " || ".join(
                [f'document.querySelector("{s}")' for s in indicators]
            )
            check_script = f"!!(({selector_js}))"

            ws = websocket.create_connection(ws_url, timeout=5)
            # Navigate to platform URL
            ws.send(json.dumps({
                "id": 1,
                "method": "Page.navigate",
                "params": {"url": url}
            }))
            time.sleep(3)

            # Evaluate login check
            ws.send(json.dumps({
                "id": 2,
                "method": "Runtime.evaluate",
                "params": {"expression": check_script, "returnByValue": True}
            }))
            result = json.loads(ws.recv())
            ws.close()

            logged_in = result.get("result", {}).get("result", {}).get("value", False)
            return {
                "logged_in": logged_in,
                "last_checked": datetime.now().isoformat(),
                "url": url,
                "cdp_port": cdp_port,
            }
        except ImportError:
            return {
                "logged_in": None,
                "error": "websocket-client not installed (pip3 install websocket-client)",
                "last_checked": datetime.now().isoformat(),
            }

    except Exception as e:
        return {
            "logged_in": None,
            "error": str(e),
            "last_checked": datetime.now().isoformat(),
            "cdp_port": cdp_port,
        }


def check_client(client_id: str, dry_run: bool = False):
    cfg = load_client(client_id)
    port = cfg.get("cdp_port")
    platforms = cfg.get("platforms", {})
    name = cfg.get("name", client_id)

    print(f"\nChecking login status for: {name} (port {port})")
    print("-" * 50)

    enabled = {p: v for p, v in platforms.items() if v.get("enabled")}
    if not enabled:
        print("  No enabled platforms.")
        return {}

    results = {}
    for platform, pdata in enabled.items():
        handle = pdata.get("handle", "")
        print(f"  Checking {platform} {handle}...", end=" ", flush=True)
        status = check_platform_via_cdp(platform, port, dry_run=dry_run)
        results[platform] = status
        if dry_run:
            print("[dry-run]")
        elif status.get("logged_in") is True:
            print("logged_in")
        elif status.get("logged_in") is False:
            print("NOT logged in")
        else:
            err = status.get("error", "unknown")
            print(f"unknown ({err})")

    if not dry_run:
        save_login_status(client_id, results)
        print(f"\nStatus saved to clients/{client_id}/login_status.json")

    return results


def list_all_clients() -> list:
    if not CLIENTS_DIR.exists():
        return []
    return [
        f.stem for f in CLIENTS_DIR.glob("*.json")
        if f.stem != "new-client-template"
    ]


def main():
    parser = argparse.ArgumentParser(description="Check platform login status via CDP")
    parser.add_argument("--client", help="Client ID (e.g. mic-mann)")
    parser.add_argument("--all", action="store_true", help="Check all clients")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually connect to CDP")
    args = parser.parse_args()

    if args.all:
        client_ids = list_all_clients()
        if not client_ids:
            print("No clients found.")
            sys.exit(0)
        for cid in client_ids:
            check_client(cid, dry_run=args.dry_run)
    elif args.client:
        check_client(args.client, dry_run=args.dry_run)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

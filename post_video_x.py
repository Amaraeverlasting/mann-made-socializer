#!/usr/bin/env python3
"""Post a video to X using agent-browser --cdp 18800"""
import argparse, json, subprocess, sys
from pathlib import Path


def post(video_path: str, caption: str, cdp_port: int = 18800):
    print(f"Posting video to X: {video_path}")
    print(f"Caption: {caption[:100]}")

    # Escape caption for JS
    safe_caption = caption[:280].replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")

    result = subprocess.run([
        "agent-browser", "--cdp", str(cdp_port),
        "script", f"""
        // Navigate to X home
        await fetch('about:blank');
        window.location.href = 'https://x.com/home';
        await new Promise(r => setTimeout(r, 3000));
        // Click compose button
        const compose = document.querySelector('[data-testid="SideNav_NewTweet_Button"]');
        if (compose) compose.click();
        await new Promise(r => setTimeout(r, 1500));
        // Type caption
        const editor = document.querySelector('[data-testid="tweetTextarea_0"]');
        if (editor) {{
            editor.focus();
            document.execCommand('insertText', false, '{safe_caption}');
        }}
        """
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error: {result.stderr[:300]}", file=sys.stderr)

    return result.returncode == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Post video to X")
    parser.add_argument("--video", required=True, help="Path to video file")
    parser.add_argument("--caption", default="", help="Post caption")
    parser.add_argument("--cdp-port", type=int, default=18800, help="Chrome CDP port")
    args = parser.parse_args()
    success = post(args.video, args.caption, args.cdp_port)
    sys.exit(0 if success else 1)

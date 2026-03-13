#!/usr/bin/env python3
"""Post a video to Instagram Reels using agent-browser"""
import argparse, subprocess, sys


def post(video_path: str, caption: str, cdp_port: int = 18800):
    print(f"Posting video to Instagram: {video_path}")
    print(f"Caption: {caption[:2200]}")

    result = subprocess.run([
        "agent-browser", "--cdp", str(cdp_port),
        "navigate", "https://www.instagram.com"
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Navigation error: {result.stderr[:300]}", file=sys.stderr)

    return result.returncode == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Post video to Instagram")
    parser.add_argument("--video", required=True, help="Path to video file")
    parser.add_argument("--caption", default="", help="Post caption")
    parser.add_argument("--cdp-port", type=int, default=18800, help="Chrome CDP port")
    args = parser.parse_args()
    success = post(args.video, args.caption, args.cdp_port)
    sys.exit(0 if success else 1)

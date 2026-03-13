#!/usr/bin/env python3
"""
generate_and_queue.py - Generate a social post via AI and publish via Postiz
Usage: python3 generate_and_queue.py --client mic-mann --platform x|linkedin --slot morning|afternoon|evening|night [--dry-run]
"""
import argparse, json, os, sys, sqlite3, httpx
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent
CLIENTS_DIR = BASE / "clients"
DB_PATH = BASE / "data" / "socializer.db"
SECRETS = json.load(open(BASE / "secrets.json"))

POSTIZ_URL = SECRETS["postiz"]["url"]
POSTIZ_KEY = SECRETS["postiz"]["apiKey"]
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

PLATFORM_PROMPTS = {
    "x": "Write one punchy X (Twitter) post for Mic Mann. Under 280 characters. Hook-first. Opinionated. Can be provocative. No hashtags unless natural. Do NOT start with 'In' or 'The'.",
    "linkedin": "Write one LinkedIn post for Mic Mann. 150-250 words. Narrative style. Start with a specific observation, fact, or number - NOT with 'I' or 'In today'. Professional but not stiff. No bullet lists."
}

SYSTEM_PROMPT = """You are writing social media posts for Mic Mann (@micmannsa), a South African tech entrepreneur. His focus: Singularity, AI, exponential technology, Africa's digital future, and PodPal (his AI podcast co-pilot).

Rules:
- No em dashes (use hyphens or commas instead)
- No AI buzzwords: leverage, seamlessly, transformative, vibrant, delve, tapestry, robust, comprehensive, groundbreaking, synergy, paradigm, empower, catalyst, invaluable
- No sycophancy, no 'exciting times', no corporate speak
- Have opinions - don't just report, react
- Be specific with facts or numbers when possible
- South African context where relevant
- Rotate themes: AI/Singularity, Africa tech, exponential thinking, PodPal, Mann Made, personal insights

Return ONLY the post text. Nothing else. No quotes around it."""


def generate_post(platform: str, slot: str) -> str:
    platform_instruction = PLATFORM_PROMPTS.get(platform, PLATFORM_PROMPTS["x"])
    user_msg = f"{platform_instruction}\n\nTime of day: {slot}"

    if OPENAI_KEY:
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            json={
                "model": "gpt-4o-mini",
                "max_tokens": 600,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg}
                ]
            },
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    elif ANTHROPIC_KEY:
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01"},
            json={
                "model": "claude-haiku-4-5",
                "max_tokens": 600,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_msg}]
            },
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"].strip()
    else:
        raise ValueError("No API key available - set OPENAI_API_KEY or ANTHROPIC_API_KEY")


def publish_to_postiz(content: str, integration_id: str) -> dict:
    resp = httpx.post(
        f"{POSTIZ_URL}/api/public/v1/posts",
        headers={"Authorization": POSTIZ_KEY, "Content-Type": "application/json"},
        json={
            "type": "now",
            "date": datetime.now(timezone.utc).isoformat(),
            "shortLink": False,
            "tags": [],
            "posts": [{"integration": {"id": integration_id}, "value": [{"content": content, "image": []}], "settings": {"who_can_reply_post": "everyone"}}]
        },
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def log_to_db(client: str, platform: str, content: str, status: str, postiz_id: str = None, error: str = None):
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, client TEXT, platform TEXT,
            content TEXT, status TEXT, postiz_id TEXT, error TEXT,
            created_at TEXT, posted_at TEXT)""")
        conn.execute(
            "INSERT INTO posts (client,platform,content,status,postiz_id,error,created_at,posted_at) VALUES (?,?,?,?,?,?,?,?)",
            (client, platform, content, status, postiz_id, error,
             datetime.utcnow().isoformat(),
             datetime.utcnow().isoformat() if status == "published" else None)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[WARN] DB log failed: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", default="mic-mann")
    parser.add_argument("--platform", required=True, choices=["x", "linkedin"])
    parser.add_argument("--slot", default="morning")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    client_path = CLIENTS_DIR / f"{args.client}.json"
    if not client_path.exists():
        print(f"ERROR: Client config not found: {client_path}")
        sys.exit(1)

    client = json.load(open(client_path))
    platform_cfg = client["platforms"].get(args.platform, {})
    integration_id = platform_cfg.get("postiz_integration_id")

    if not integration_id and not args.dry_run:
        print(f"ERROR: No postiz_integration_id for {args.platform} in {args.client}")
        sys.exit(1)

    print(f"[{args.client}] Generating {args.platform} post for slot: {args.slot}")
    content = generate_post(args.platform, args.slot)
    print(f"\n--- Generated content ---\n{content}\n-------------------------")

    if args.dry_run:
        print("[DRY RUN] Not posting.")
        return

    print(f"\nPublishing via Postiz (integration: {integration_id})...")
    try:
        result = publish_to_postiz(content, integration_id)
        print(f"[OK] Published. Response: {str(result)[:200]}")
        post_id = result[0].get("postId", "") if isinstance(result, list) else str(result.get("id", ""))
        log_to_db(args.client, args.platform, content, "published", post_id)
    except Exception as e:
        print(f"[ERROR] {e}")
        log_to_db(args.client, args.platform, content, "failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()

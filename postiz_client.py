"""Postiz API client for Mann Made Socializer."""
import httpx
import json
import os
from pathlib import Path
from typing import Optional

# Load config from secrets.json if present, fall back to env vars
_SECRETS_FILE = Path(__file__).parent / "secrets.json"


def _load_postiz_config() -> dict:
    if _SECRETS_FILE.exists():
        try:
            data = json.loads(_SECRETS_FILE.read_text())
            return data.get("postiz", {})
        except Exception:
            pass
    return {}


_cfg = _load_postiz_config()

POSTIZ_URL = os.environ.get("POSTIZ_URL") or _cfg.get("localUrl") or _cfg.get("url") or "http://localhost:4007"
POSTIZ_API = f"{POSTIZ_URL}/api"


class PostizClient:
    """Async HTTP client wrapping the Postiz REST API."""

    def __init__(self, api_key: str = ""):
        cfg = _load_postiz_config()
        self.api_key = api_key or cfg.get("apiKey", "")
        self.base_url = POSTIZ_API
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------ #
    #  Health                                                              #
    # ------------------------------------------------------------------ #

    async def health(self) -> dict:
        """Return basic health status of the Postiz instance."""
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                r = await client.get(f"{POSTIZ_URL}/api/status", headers=self.headers)
                return {"ok": r.status_code < 500, "status_code": r.status_code, "body": r.text[:200]}
            except Exception as e:
                return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------------ #
    #  Channels (connected social accounts)                               #
    # ------------------------------------------------------------------ #

    async def get_channels(self) -> list:
        """Return all connected social accounts (integrations) from Postiz."""
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{self.base_url}/integrations",
                headers=self.headers,
            )
            r.raise_for_status()
            data = r.json()
            # Postiz may wrap in {"integrations": [...]} or return list directly
            if isinstance(data, list):
                return data
            return data.get("integrations", data.get("channels", []))

    # ------------------------------------------------------------------ #
    #  Posts                                                               #
    # ------------------------------------------------------------------ #

    async def get_posts(self, status: str = "pending") -> list:
        """Return scheduled or published posts from Postiz."""
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{self.base_url}/posts",
                headers=self.headers,
                params={"status": status},
            )
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                return data
            return data.get("posts", [])

    async def create_post(
        self,
        content: str,
        platforms: list,
        scheduled_at: Optional[str] = None,
        media_url: Optional[str] = None,
    ) -> dict:
        """Schedule a post to one or more Postiz channels.

        Args:
            content:      Post text/body.
            platforms:    List of Postiz integration IDs or platform names.
            scheduled_at: ISO-8601 datetime string. None = publish immediately.
            media_url:    Optional public URL of media to attach.
        """
        payload: dict = {
            "content": content,
            "integrations": platforms,
        }
        if scheduled_at:
            payload["scheduleDate"] = scheduled_at
        if media_url:
            payload["media"] = [{"url": media_url}]

        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{self.base_url}/posts",
                headers=self.headers,
                json=payload,
            )
            r.raise_for_status()
            return r.json()

    async def delete_post(self, post_id: str) -> bool:
        """Cancel / delete a scheduled post from Postiz."""
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.delete(
                f"{self.base_url}/posts/{post_id}",
                headers=self.headers,
            )
            return r.status_code in (200, 204)

    # ------------------------------------------------------------------ #
    #  OAuth connect                                                       #
    # ------------------------------------------------------------------ #

    async def get_connect_url(self, provider: str) -> dict:
        """Return the OAuth redirect URL to connect a new social account.

        Args:
            provider: e.g. "x", "linkedin", "instagram", "tiktok", "facebook"
        """
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{self.base_url}/integrations/{provider}/connect",
                headers=self.headers,
            )
            r.raise_for_status()
            return r.json()

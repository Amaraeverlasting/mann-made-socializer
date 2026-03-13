"""Mann Made Socializer Platform - server.py"""
import json, uuid, subprocess, os, shutil, sys, asyncio, re
from datetime import datetime, date, timedelta
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

# Clipper engine (sibling module)
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from clipper.engine import process_video as _clipper_process_video
    _clipper_ok = True
except Exception as _e:
    print(f"[WARN] Clipper engine failed to load: {_e}")
    _clipper_ok = False

# Auth imports
from auth import (
    get_current_user, require_auth, require_admin, require_editor_or_above,
    handle_login, handle_logout, handle_me,
    handle_list_users, handle_create_user, handle_delete_user, handle_change_role,
)

# ---------------------------------------------------------------------------
# Routes that do NOT require authentication
# ---------------------------------------------------------------------------
PUBLIC_PATHS = {
    "/login",
    "/api/auth/login",
    "/api/health",
}

try:
    import anthropic as _anthropic_module
except ImportError:
    _anthropic_module = None

BASE = Path(__file__).parent
CLIENTS_DIR = BASE / "clients"
ACCOUNTS_FILE = Path.home() / ".openclaw/workspace/skills/socializer/accounts.json"
QUEUE_FILE = Path.home() / ".openclaw/workspace/skills/socializer/queue.json"
SESSIONS_DIR = Path.home() / ".openclaw/workspace/browser-sessions"
TEMPLATES_FILE = BASE / "templates.json"
VIDEOS_DIR = BASE / "videos"
VIDEO_QUEUE_FILE = BASE / "video_queue.json"

DEFAULT_TEMPLATES = [
    {
        "id": "thought-leadership",
        "name": "Thought Leadership",
        "description": "Share a bold opinion or insight",
        "platforms": ["x", "linkedin"],
        "template": "Most people think [common belief]. Here's what actually happens:\n\n[Your contrarian insight]\n\n[Evidence or example]\n\n[Implication or question]",
        "tone": "bold"
    },
    {
        "id": "story-lesson",
        "name": "Story + Lesson",
        "description": "Personal story with a takeaway",
        "platforms": ["linkedin", "facebook"],
        "template": "[Specific situation or observation].\n\n[What happened / what you noticed].\n\n[The lesson or shift in thinking].\n\n[Question to audience]",
        "tone": "conversational"
    },
    {
        "id": "stat-insight",
        "name": "Stat + Insight",
        "description": "Lead with a number, follow with context",
        "platforms": ["x", "linkedin"],
        "template": "[Surprising stat or fact].\n\n[Why this matters].\n\n[What most people miss].",
        "tone": "professional"
    },
    {
        "id": "hot-take",
        "name": "Hot Take",
        "description": "Short contrarian opinion for X",
        "platforms": ["x"],
        "template": "[Controversial statement].\n\nHere's why: [reason in 1-2 sentences].",
        "tone": "bold"
    },
    {
        "id": "product-update",
        "name": "Product / Project Update",
        "description": "Share what you're building",
        "platforms": ["x", "linkedin"],
        "template": "Built [thing] this week.\n\n[What it does in one sentence].\n\n[Why you built it / problem it solves].\n\n[Next step or call to action].",
        "tone": "casual"
    },
    {
        "id": "question-engagement",
        "name": "Question for Engagement",
        "description": "Ask your audience something",
        "platforms": ["x", "linkedin", "facebook"],
        "template": "[Specific question about your topic]?\n\n[1-2 sentences of context to explain why you're asking].",
        "tone": "conversational"
    },
    {
        "id": "africa-insight",
        "name": "Africa + Tech Insight",
        "description": "AI/tech angle with African context",
        "platforms": ["linkedin", "x"],
        "template": "[Global tech trend or stat].\n\nIn Africa: [specific local angle, country, or example].\n\n[Opportunity or challenge this creates].\n\n[What needs to happen next].",
        "tone": "professional"
    },
    {
        "id": "event-promo",
        "name": "Event Promotion",
        "description": "Promote an event or appearance",
        "platforms": ["linkedin", "x", "facebook", "instagram"],
        "template": "[Event name] is [date].\n\n[What it is in one sentence].\n\n[Why people should come / what they'll get].\n\n[Link or CTA].",
        "tone": "professional"
    },
    {
        "id": "tiktok-hook",
        "name": "TikTok Hook",
        "description": "Short punchy TikTok caption",
        "platforms": ["tiktok"],
        "template": "[Hook in 3-5 words] #[tag1] #[tag2]",
        "tone": "casual"
    },
    {
        "id": "weekly-recap",
        "name": "Weekly Recap",
        "description": "End of week summary post",
        "platforms": ["linkedin", "facebook"],
        "template": "This week:\n\n- [Thing 1]\n- [Thing 2]\n- [Thing 3]\n\n[Reflection or what's next].",
        "tone": "conversational"
    }
]

DEFAULT_TEMPLATE_IDS = {t["id"] for t in DEFAULT_TEMPLATES}

def load_templates():
    if TEMPLATES_FILE.exists():
        return json.loads(TEMPLATES_FILE.read_text())
    return list(DEFAULT_TEMPLATES)

def load_tracker():
    tracker = Path.home() / ".openclaw/workspace/data/posted_tracker.json"
    if not tracker.exists():
        return []
    data = json.loads(tracker.read_text())
    if isinstance(data, list):
        return data
    return data.get("posts", [])

app = FastAPI()


# ---------------------------------------------------------------------------
# Auth middleware: protect all /api/* routes (except public paths)
# ---------------------------------------------------------------------------
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Always allow public paths
        if path in PUBLIC_PATHS:
            return await call_next(request)

        # Allow static assets without auth
        if not path.startswith("/api/"):
            return await call_next(request)

        # /api/* routes require a valid token
        user = get_current_user(request)
        if not user:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)

        return await call_next(request)


app.add_middleware(AuthMiddleware)

# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page - redirect to home if already authenticated."""
    user = get_current_user(request)
    if user:
        return RedirectResponse("/", status_code=302)
    return (BASE / "login.html").read_text()


@app.post("/api/auth/login")
async def auth_login(request: Request):
    return await handle_login(request)


@app.post("/api/auth/logout")
async def auth_logout(request: Request):
    return await handle_logout(request)


@app.get("/api/auth/me")
async def auth_me(request: Request):
    return await handle_me(request)


@app.get("/api/health")
async def health():
    return {"ok": True, "service": "mann-made-socializer"}


# User management (admin only)

@app.get("/api/auth/users")
async def list_users(request: Request):
    return await handle_list_users(request)


@app.post("/api/auth/users")
async def create_user(request: Request):
    return await handle_create_user(request)


@app.delete("/api/auth/users/{email:path}")
async def delete_user(request: Request, email: str):
    return await handle_delete_user(request, email)


@app.put("/api/auth/users/{email:path}/role")
async def change_role(request: Request, email: str):
    return await handle_change_role(request, email)


# ---------------------------------------------------------------------------
# Protected page routes - redirect to login if not authenticated
# ---------------------------------------------------------------------------

@app.middleware("http")
async def page_auth_redirect(request: Request, call_next):
    """For HTML page routes, redirect unauthenticated users to /login."""
    path = request.url.path
    # Only redirect for known HTML pages (not /api/*, not /login)
    html_pages = {"/", "/clients", "/analytics"}
    if path in html_pages:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(f"/login?next={path}", status_code=302)
    return await call_next(request)


# ---------------------------------------------------------------------------
# App data helpers
# ---------------------------------------------------------------------------

def load_accounts():
    if ACCOUNTS_FILE.exists():
        return json.loads(ACCOUNTS_FILE.read_text()).get("accounts", [])
    return []

def load_queue():
    if QUEUE_FILE.exists():
        return json.loads(QUEUE_FILE.read_text())
    return []

def save_queue(posts):
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_FILE.write_text(json.dumps(posts, indent=2))

@app.get("/", response_class=HTMLResponse)
async def index():
    return (BASE / "index.html").read_text()

@app.get("/clients", response_class=HTMLResponse)
async def clients_page():
    return (BASE / "clients.html").read_text()

@app.get("/api/accounts")
async def get_accounts():
    accounts = load_accounts()
    for acc in accounts:
        session_path = SESSIONS_DIR / acc.get("session_file", "")
        acc["connected"] = session_path.exists()
    return accounts

@app.post("/api/accounts/{acc_id}/activate")
async def toggle_account(acc_id: str, request: Request):
    body = await request.json()
    data = json.loads(ACCOUNTS_FILE.read_text())
    for acc in data["accounts"]:
        if acc["id"] == acc_id:
            acc["active"] = body.get("active", not acc.get("active", False))
    ACCOUNTS_FILE.write_text(json.dumps(data, indent=2))
    return {"ok": True}

@app.get("/api/posts")
async def get_posts(status: str = "", account: str = "", platform: str = ""):
    posts = load_queue()
    if status:
        posts = [p for p in posts if p.get("status") == status]
    if account:
        posts = [p for p in posts if account in p.get("account_ids", [])]
    if platform:
        accounts = {a["id"]: a for a in load_accounts()}
        posts = [p for p in posts if any(accounts.get(aid, {}).get("platform") == platform for aid in p.get("account_ids", []))]
    return sorted(posts, key=lambda x: x.get("scheduled_at") or x.get("created_at") or "", reverse=True)

@app.post("/api/posts")
async def create_post(request: Request):
    body = await request.json()
    user = get_current_user(request)
    role = (user or {}).get("role", "viewer")
    # Approval workflow: editors need approval, admins go straight to scheduled
    if role == "editor":
        initial_status = "pending_approval"
    else:
        initial_status = "scheduled" if body.get("scheduled_at") else "draft"

    post = {
        "id": str(uuid.uuid4())[:8],
        "account_ids": body.get("account_ids", []),
        "content": body.get("content", ""),
        "media": body.get("media", []),
        "media_type": body.get("media_type", "none"),
        "status": initial_status,
        "per_account_status": {aid: "pending" for aid in body.get("account_ids", [])},
        "scheduled_at": body.get("scheduled_at"),
        "posted_at": None,
        "created_at": datetime.now().isoformat(),
        "tags": body.get("tags", []),
        "campaign": body.get("campaign"),
        "client_id": body.get("client_id", ""),
        "rejection_reason": None,
        "platform": body.get("platform", ""),
    }
    posts = load_queue()
    posts.append(post)
    save_queue(posts)
    return post

@app.put("/api/posts/{post_id}")
async def update_post(post_id: str, request: Request):
    body = await request.json()
    posts = load_queue()
    for p in posts:
        if p["id"] == post_id:
            p.update({k: v for k, v in body.items() if k != "id"})
            if p.get("scheduled_at") and p["status"] == "draft":
                p["status"] = "scheduled"
            save_queue(posts)
            return p
    raise HTTPException(404, "Post not found")

@app.delete("/api/posts/{post_id}")
async def delete_post(post_id: str):
    posts = load_queue()
    posts = [p for p in posts if p["id"] != post_id]
    save_queue(posts)
    return {"ok": True}

@app.post("/api/posts/{post_id}/post-now")
async def post_now(post_id: str):
    posts = load_queue()
    for p in posts:
        if p["id"] == post_id:
            p["status"] = "scheduled"
            p["scheduled_at"] = datetime.now().isoformat()
            save_queue(posts)
            return {"ok": True, "message": "Queued for immediate posting"}
    raise HTTPException(404, "Not found")

@app.get("/api/calendar")
async def get_calendar(year: int = None, month: int = None):
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    posts = load_queue()
    cal = {}
    for p in posts:
        dt_str = p.get("scheduled_at") or p.get("posted_at") or ""
        if dt_str:
            try:
                dt = datetime.fromisoformat(dt_str)
                if dt.year == year and dt.month == month:
                    day = str(dt.day)
                    cal.setdefault(day, []).append(p)
            except: pass
    return {"year": year, "month": month, "days": cal}

@app.get("/api/stats")
async def get_stats():
    posts = load_queue()
    now = datetime.now()
    today = now.date().isoformat()
    week_start = now.isocalendar()[1]
    return {
        "total": len(posts),
        "scheduled": sum(1 for p in posts if p.get("status") == "scheduled"),
        "draft": sum(1 for p in posts if p.get("status") == "draft"),
        "posted": sum(1 for p in posts if p.get("status") == "posted"),
        "failed": sum(1 for p in posts if p.get("status") == "failed"),
        "today": sum(1 for p in posts if (p.get("scheduled_at") or "").startswith(today)),
        "accounts_active": sum(1 for a in load_accounts() if a.get("active"))
    }

@app.get("/api/analytics")
async def get_analytics(days: int = 30):
    snapshots_file = BASE / "analytics/snapshots.json"
    snapshots = []
    if snapshots_file.exists():
        all_snaps = json.loads(snapshots_file.read_text())
        cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
        snapshots = [s for s in all_snaps if s.get("date", "") >= cutoff]

    # Latest snapshot
    latest = snapshots[-1] if snapshots else {}

    # Growth: compare today vs 7 days ago
    week_ago_snap = next((s for s in reversed(snapshots) if s.get("date", "") <= (datetime.now() - timedelta(days=7)).date().isoformat()), {})
    growth_7d = latest.get("posts_total", 0) - week_ago_snap.get("posts_total", 0)

    return {
        "latest": latest,
        "snapshots": snapshots,
        "growth_7d": growth_7d,
        "days_tracked": len(snapshots)
    }

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page():
    analytics_html = BASE / "analytics.html"
    if analytics_html.exists():
        return analytics_html.read_text()
    raise HTTPException(404, "analytics.html not found")

# ===== TEMPLATES =====

@app.get("/api/templates")
async def get_templates():
    return load_templates()

@app.post("/api/templates")
async def save_template(request: Request):
    body = await request.json()
    templates = load_templates()
    body["id"] = body.get("id") or str(uuid.uuid4())[:8]
    body["is_custom"] = True
    templates.append(body)
    TEMPLATES_FILE.write_text(json.dumps(templates, indent=2))
    return body

@app.delete("/api/templates/{template_id}")
async def delete_template(template_id: str):
    if template_id in DEFAULT_TEMPLATE_IDS:
        raise HTTPException(400, "Cannot delete default templates")
    templates = [t for t in load_templates() if t["id"] != template_id]
    TEMPLATES_FILE.write_text(json.dumps(templates, indent=2))
    return {"ok": True}

# ===== AI CONTENT GENERATION =====

@app.post("/api/generate")
async def generate_content(request: Request):
    body = await request.json()
    topic = body.get("topic", "")
    url = body.get("url", "")
    account_ids = body.get("account_ids", [])
    tone = body.get("tone", "professional")

    if not topic and not url:
        raise HTTPException(400, "Provide a topic or URL")

    if _anthropic_module is None:
        raise HTTPException(503, "anthropic package not installed. Run: pip3 install anthropic")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(503, "ANTHROPIC_API_KEY not set")

    accounts = load_accounts()
    platforms = list(set(
        a["platform"] for a in accounts
        if a["id"] in account_ids
    ))

    if not platforms:
        raise HTTPException(400, "No valid accounts selected")

    client = _anthropic_module.Anthropic(api_key=api_key)

    recent_posts = load_tracker()[-10:]
    recent_sample = "\n".join([
        f"[{p.get('platform','?')}] {(p.get('text') or p.get('content',''))[:150]}"
        for p in recent_posts
    ]) or "(no recent posts)"

    platform_rules = {
        "x": "Max 280 chars. No hashtag spam. Start with the idea. Short sentences.",
        "linkedin": "Max 1500 chars. No day/time openers. Start with the observation. 3-4 short paragraphs. End with a question.",
        "instagram": "Max 2200 chars. Visual storytelling. 3-5 relevant hashtags at end.",
        "facebook": "Conversational. 1-3 paragraphs. Can be longer than X.",
        "tiktok": "Short punchy caption. 1-2 lines. Hook in first 3 words.",
        "youtube": "Descriptive. SEO-friendly. Include keywords naturally.",
    }

    posts = {}
    for platform in platforms:
        rules = platform_rules.get(platform, "Keep it concise and engaging.")
        prompt = f"""Write a social media post for {platform} about: {topic or url}

Platform rules: {rules}

Tone: {tone}

Recent posts by this account for reference (match this voice):
{recent_sample}

Rules:
- No em dashes (long dashes)
- No AI filler phrases (delve, tapestry, vibrant, comprehensive, etc)
- No sycophantic openers
- Sound human and specific
- No hashtag spam

Return ONLY the post text, nothing else."""

        message = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        posts[platform] = message.content[0].text.strip()

    return {"posts": posts, "topic": topic, "url": url}

# ===== VIDEO QUEUE =====

def load_video_queue():
    if VIDEO_QUEUE_FILE.exists():
        return json.loads(VIDEO_QUEUE_FILE.read_text())
    return []

def save_video_queue(items):
    VIDEO_QUEUE_FILE.write_text(json.dumps(items, indent=2))

@app.get("/api/videos")
async def get_videos():
    return load_video_queue()

@app.get("/api/videos/stats")
async def video_stats():
    queue = load_video_queue()
    return {
        "total": len(queue),
        "scheduled": sum(1 for v in queue if v.get("status") == "scheduled"),
        "posted": sum(1 for v in queue if v.get("status") == "posted"),
        "draft": sum(1 for v in queue if v.get("status") == "draft"),
        "failed": sum(1 for v in queue if v.get("status") == "failed"),
        "partial": sum(1 for v in queue if v.get("status") == "partial"),
    }

@app.post("/api/videos/upload")
async def upload_video(
    file: UploadFile = File(...),
    account_ids: str = Form(...),
    caption: str = Form(""),
    scheduled_at: str = Form(""),
    campaign: str = Form("")
):
    inbox = VIDEOS_DIR / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)

    file_path = inbox / file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    aid_list = [a.strip() for a in account_ids.split(",") if a.strip()]

    item = {
        "id": str(uuid.uuid4())[:8],
        "filename": file.filename,
        "file_path": str(file_path),
        "account_ids": aid_list,
        "caption": caption,
        "scheduled_at": scheduled_at or None,
        "campaign": campaign,
        "status": "scheduled" if scheduled_at else "draft",
        "per_account_status": {aid: "pending" for aid in aid_list},
        "created_at": datetime.now().isoformat(),
        "posted_at": None,
        "type": "video"
    }

    queue = load_video_queue()
    queue.append(item)
    save_video_queue(queue)
    return item

@app.delete("/api/videos/{video_id}")
async def delete_video(video_id: str):
    queue = load_video_queue()
    item = next((v for v in queue if v["id"] == video_id), None)
    if item:
        try:
            Path(item["file_path"]).unlink(missing_ok=True)
        except Exception:
            pass
    queue = [v for v in queue if v["id"] != video_id]
    save_video_queue(queue)
    return {"ok": True}


# ===== CLIENTS API =====

def load_all_clients() -> list:
    """Load all client configs from clients/ directory."""
    clients = []
    if not CLIENTS_DIR.exists():
        return clients
    for f in sorted(CLIENTS_DIR.glob("*.json")):
        if f.stem == "new-client-template":
            continue
        try:
            data = json.loads(f.read_text())
            clients.append(data)
        except Exception:
            pass
    return clients


def load_client(client_id: str) -> dict:
    f = CLIENTS_DIR / f"{client_id}.json"
    if not f.exists():
        raise HTTPException(404, f"Client '{client_id}' not found")
    return json.loads(f.read_text())


def save_client(cfg: dict):
    CLIENTS_DIR.mkdir(parents=True, exist_ok=True)
    f = CLIENTS_DIR / f"{cfg['id']}.json"
    f.write_text(json.dumps(cfg, indent=2))


@app.get("/api/clients")
async def get_clients():
    return load_all_clients()


@app.get("/api/clients/next-port")
async def next_port_early():
    """Get the next available CDP port. Defined early to avoid conflict with {client_id} route."""
    clients = load_all_clients()
    used_ports = {c.get("cdp_port", 0) for c in clients}
    port = 18800
    while port in used_ports:
        port += 1
    return {"port": port}


@app.get("/api/clients/{client_id}")
async def get_client(client_id: str):
    return load_client(client_id)


@app.post("/api/clients")
async def create_client(request: Request):
    body = await request.json()
    client_id = body.get("id", "").strip()
    if not client_id:
        raise HTTPException(400, "Client 'id' is required")
    existing = CLIENTS_DIR / f"{client_id}.json"
    if existing.exists():
        raise HTTPException(409, f"Client '{client_id}' already exists")
    if not body.get("created_at"):
        body["created_at"] = datetime.now().isoformat()
    save_client(body)
    # Create content folder if specified
    folder = body.get("content_folder", "")
    if folder:
        try:
            Path(folder).mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
    return body


@app.put("/api/clients/{client_id}")
async def update_client(client_id: str, request: Request):
    load_client(client_id)  # 404 if not found
    body = await request.json()
    body["id"] = client_id  # ensure ID matches path
    save_client(body)
    return body


@app.get("/api/clients/{client_id}/queue")
async def get_client_queue(client_id: str):
    cfg = load_client(client_id)
    folder = cfg.get("content_folder", "")
    items = []
    if folder and Path(folder).exists():
        for f in sorted(Path(folder).iterdir()):
            if f.is_file() and not f.name.startswith("."):
                items.append({
                    "filename": f.name,
                    "path": str(f),
                    "size": f.stat().st_size,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                })
    return {
        "client_id": client_id,
        "client_name": cfg.get("name", client_id),
        "folder": folder,
        "sheet_id": cfg.get("sheet_id", ""),
        "items": items,
        "count": len(items)
    }



# ===== EXTENDED CLIENT QUEUE API =====

def get_client_queue_file(client_id: str) -> Path:
    return CLIENTS_DIR / client_id / "queue.json"

def load_client_queue_data(client_id: str) -> list:
    qf = get_client_queue_file(client_id)
    if qf.exists():
        try:
            return json.loads(qf.read_text())
        except Exception:
            return []
    return []

def save_client_queue_data(client_id: str, items: list):
    qdir = CLIENTS_DIR / client_id
    qdir.mkdir(parents=True, exist_ok=True)
    qf = qdir / "queue.json"
    qf.write_text(json.dumps(items, indent=2))


@app.get("/api/clients/{client_id}/queue/items")
async def list_queue_items(client_id: str, status: str = ""):
    load_client(client_id)  # 404 check
    items = load_client_queue_data(client_id)
    if status:
        items = [i for i in items if i.get("status") == status]
    return {"client_id": client_id, "items": items, "count": len(items)}


@app.post("/api/clients/{client_id}/queue/items")
async def add_queue_item(client_id: str, request: Request):
    load_client(client_id)  # 404 check
    body = await request.json()
    item = {
        "id": str(uuid.uuid4())[:8],
        "filename": body.get("filename", ""),
        "caption": body.get("caption", ""),
        "platforms": body.get("platforms", []),
        "scheduled": body.get("scheduled", ""),
        "status": body.get("status", "pending"),
        "created_at": datetime.now().isoformat(),
        "posted_at": None,
        "error": None,
    }
    items = load_client_queue_data(client_id)
    items.append(item)
    save_client_queue_data(client_id, items)
    return item


@app.put("/api/clients/{client_id}/queue/items/{item_id}")
async def update_queue_item(client_id: str, item_id: str, request: Request):
    load_client(client_id)
    body = await request.json()
    items = load_client_queue_data(client_id)
    for item in items:
        if item["id"] == item_id:
            item.update({k: v for k, v in body.items() if k != "id"})
            save_client_queue_data(client_id, items)
            return item
    raise HTTPException(404, f"Queue item '{item_id}' not found")


@app.delete("/api/clients/{client_id}/queue/items/{item_id}")
async def delete_queue_item(client_id: str, item_id: str):
    load_client(client_id)
    items = load_client_queue_data(client_id)
    new_items = [i for i in items if i["id"] != item_id]
    if len(new_items) == len(items):
        raise HTTPException(404, f"Queue item '{item_id}' not found")
    save_client_queue_data(client_id, new_items)
    return {"ok": True}


@app.post("/api/clients/{client_id}/queue/scan")
async def scan_inbox(client_id: str):
    """Scan client's inbox folder and auto-add new files to queue."""
    cfg = load_client(client_id)
    folder = cfg.get("content_folder", "")
    if not folder:
        raise HTTPException(400, "No content_folder configured for this client")

    inbox = Path(folder)
    if not inbox.exists():
        inbox.mkdir(parents=True, exist_ok=True)
        return {"added": 0, "message": "Inbox folder created (was empty)"}

    # Load existing queue to avoid duplicates
    existing = load_client_queue_data(client_id)
    existing_filenames = {i["filename"] for i in existing}

    # Check for queue.json in inbox
    queue_json_file = inbox / "queue.json"
    new_items = []

    if queue_json_file.exists():
        try:
            raw = json.loads(queue_json_file.read_text())
            for entry in raw:
                fname = entry.get("file", "")
                if fname and fname not in existing_filenames:
                    item = {
                        "id": str(uuid.uuid4())[:8],
                        "filename": fname,
                        "caption": entry.get("caption", ""),
                        "platforms": entry.get("platforms", list(cfg.get("platforms", {}).keys())),
                        "scheduled": entry.get("scheduled", ""),
                        "status": "pending",
                        "created_at": datetime.now().isoformat(),
                        "posted_at": None,
                        "error": None,
                        "source": "queue.json",
                    }
                    new_items.append(item)
                    existing_filenames.add(fname)
        except Exception as e:
            pass

    # Scan for media files with matching .txt captions
    MEDIA_EXT = {".mp4", ".mov", ".jpg", ".jpeg", ".png", ".gif", ".webp"}
    for f in sorted(inbox.iterdir()):
        if not f.is_file():
            continue
        if f.suffix.lower() not in MEDIA_EXT:
            continue
        if f.name in existing_filenames:
            continue
        # Look for matching caption file
        caption = ""
        caption_file = inbox / (f.stem + ".txt")
        if caption_file.exists():
            caption = caption_file.read_text().strip()

        enabled_platforms = [p for p, v in cfg.get("platforms", {}).items() if v.get("enabled")]
        item = {
            "id": str(uuid.uuid4())[:8],
            "filename": f.name,
            "caption": caption,
            "platforms": enabled_platforms,
            "scheduled": "",
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "posted_at": None,
            "error": None,
            "source": "scan",
        }
        new_items.append(item)
        existing_filenames.add(f.name)

    if new_items:
        existing.extend(new_items)
        save_client_queue_data(client_id, existing)

    return {
        "added": len(new_items),
        "total": len(existing),
        "items": new_items,
        "message": f"Scanned {folder}: added {len(new_items)} new item(s)"
    }


# ===== CLIENT ANALYTICS =====

@app.get("/api/clients/{client_id}/analytics")
async def client_analytics(client_id: str):
    cfg = load_client(client_id)
    items = load_client_queue_data(client_id)
    now = datetime.now()
    week_start = now - timedelta(days=now.weekday())

    posted = [i for i in items if i.get("status") == "posted"]
    pending = [i for i in items if i.get("status") == "pending"]
    failed = [i for i in items if i.get("status") == "failed"]

    # Posts this week
    this_week = [
        i for i in posted
        if i.get("posted_at") and datetime.fromisoformat(i["posted_at"]) >= week_start
    ]

    # Posts per platform
    by_platform = {}
    for i in posted:
        for p in (i.get("platforms") or []):
            by_platform[p] = by_platform.get(p, 0) + 1

    return {
        "client_id": client_id,
        "client_name": cfg.get("name", client_id),
        "total_queued": len(items),
        "posted": len(posted),
        "pending": len(pending),
        "failed": len(failed),
        "this_week": len(this_week),
        "by_platform": by_platform,
    }


@app.get("/api/clients/{client_id}/posts/recent")
async def client_recent_posts(client_id: str, limit: int = 10):
    load_client(client_id)
    items = load_client_queue_data(client_id)
    posted = sorted(
        [i for i in items if i.get("status") == "posted" and i.get("posted_at")],
        key=lambda x: x["posted_at"],
        reverse=True
    )
    return {"items": posted[:limit]}


# ===== CLIENT MANAGEMENT ACTIONS =====

@app.post("/api/clients/{client_id}/pause")
async def pause_client(client_id: str):
    cfg = load_client(client_id)
    cfg["status"] = "paused"
    save_client(cfg)
    return {"ok": True, "status": "paused"}


@app.post("/api/clients/{client_id}/resume")
async def resume_client(client_id: str):
    cfg = load_client(client_id)
    cfg["status"] = "active"
    save_client(cfg)
    return {"ok": True, "status": "active"}


@app.post("/api/clients/{client_id}/onboard")
async def onboard_client(client_id: str):
    cfg = load_client(client_id)
    script = BASE / "scripts" / "onboard_client.py"
    if not script.exists():
        raise HTTPException(404, "onboard_client.py script not found")
    try:
        result = subprocess.run(
            ["python3", str(script), "--client", client_id],
            capture_output=True, text=True, timeout=30
        )
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Script timed out after 30s"}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/clients/{client_id}/status")
async def client_status(client_id: str):
    cfg = load_client(client_id)
    port = cfg.get("cdp_port")
    platforms = cfg.get("platforms", {})

    # Check if CDP port is reachable
    import socket
    cdp_reachable = False
    if port:
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=1)
            s.close()
            cdp_reachable = True
        except Exception:
            cdp_reachable = False

    # Load last login status if available
    status_file = CLIENTS_DIR / client_id / "login_status.json"
    login_status = {}
    if status_file.exists():
        try:
            login_status = json.loads(status_file.read_text())
        except Exception:
            pass

    platform_status = {}
    for p, v in platforms.items():
        if v.get("enabled"):
            ls = login_status.get(p, {})
            platform_status[p] = {
                "enabled": True,
                "handle": v.get("handle", ""),
                "logged_in": ls.get("logged_in"),
                "last_checked": ls.get("last_checked"),
            }

    return {
        "client_id": client_id,
        "client_name": cfg.get("name", client_id),
        "status": cfg.get("status", "unknown"),
        "cdp_port": port,
        "cdp_reachable": cdp_reachable,
        "platforms": platform_status,
    }


# ===== NEXT AVAILABLE CDP PORT =====

@app.get("/api/clients/next-port")
async def next_port():
    clients = load_all_clients()
    used_ports = {c.get("cdp_port", 0) for c in clients}
    port = 18800
    while port in used_ports:
        port += 1
    return {"port": port}


# ===== POSTIZ INTEGRATION =====

def _load_postiz_secrets() -> dict:
    # Check ~/.openclaw/secrets.json first, then local secrets.json
    for path in [Path.home() / ".openclaw/secrets.json", BASE / "secrets.json"]:
        if path.exists():
            try:
                return json.loads(path.read_text()).get("postiz", {})
            except Exception:
                pass
    return {}


def _postiz_base_url() -> str:
    cfg = _load_postiz_secrets()
    return os.environ.get("POSTIZ_URL") or cfg.get("localUrl") or cfg.get("url") or "http://localhost:5001"


def _postiz_api_key() -> str:
    cfg = _load_postiz_secrets()
    return os.environ.get("POSTIZ_API_KEY") or cfg.get("apiKey") or ""


@app.get("/api/postiz/status")
async def postiz_status():
    """Check whether the Postiz instance is reachable."""
    import httpx
    base = _postiz_base_url()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{base}/api/status")
            return {"ok": r.status_code < 500, "status_code": r.status_code, "url": base}
    except Exception as e:
        return {"ok": False, "error": str(e), "url": base}


@app.get("/api/postiz/channels")
async def postiz_channels():
    """List all connected social accounts from Postiz."""
    import httpx
    base = _postiz_base_url()
    api_key = _postiz_api_key()
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{base}/api/integrations", headers=headers)
            r.raise_for_status()
            data = r.json()
            channels = data if isinstance(data, list) else data.get("integrations", data.get("channels", []))
            return {"ok": True, "channels": channels}
    except Exception as e:
        return {"ok": False, "error": str(e), "channels": []}


@app.post("/api/postiz/schedule")
async def postiz_schedule(request: Request):
    """Schedule a post via Postiz.

    Body: { content, platforms, scheduled_at (ISO string, optional), media_url (optional) }
    """
    import httpx
    body = await request.json()
    content = body.get("content", "")
    platforms = body.get("platforms", [])
    scheduled_at = body.get("scheduled_at")
    media_url = body.get("media_url")

    if not content:
        raise HTTPException(400, "content is required")
    if not platforms:
        raise HTTPException(400, "platforms list is required")

    base = _postiz_base_url()
    api_key = _postiz_api_key()
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    payload: dict = {"content": content, "integrations": platforms}
    if scheduled_at:
        payload["scheduleDate"] = scheduled_at
    if media_url:
        payload["media"] = [{"url": media_url}]

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(f"{base}/api/posts", headers=headers, json=payload)
            r.raise_for_status()
            return {"ok": True, "post": r.json()}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/postiz/posts")
async def postiz_posts(status: str = "pending"):
    """List scheduled or published posts from Postiz."""
    import httpx
    base = _postiz_base_url()
    api_key = _postiz_api_key()
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{base}/api/posts", headers=headers, params={"status": status})
            r.raise_for_status()
            data = r.json()
            posts = data if isinstance(data, list) else data.get("posts", [])
            return {"ok": True, "posts": posts}
    except Exception as e:
        return {"ok": False, "error": str(e), "posts": []}


@app.post("/api/postiz/clients/{client_id}/connect")
async def postiz_connect_platform(client_id: str, request: Request):
    """Return Postiz OAuth connect URL for a given platform/provider."""
    import httpx
    body = await request.json()
    provider = body.get("provider", "")
    if not provider:
        raise HTTPException(400, "provider is required (e.g. x, linkedin, instagram, tiktok)")

    base = _postiz_base_url()
    api_key = _postiz_api_key()
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{base}/api/integrations/{provider}/connect", headers=headers)
            r.raise_for_status()
            return {"ok": True, "connect_url": r.json()}
    except Exception as e:
        raise HTTPException(500, str(e))



# ===== SHEET QUEUE (Google Drive + Google Sheet pipeline) =====

def _load_secrets() -> dict:
    """Load full secrets.json from mann-made-media directory."""
    for path in [BASE / "secrets.json", Path.home() / ".openclaw/secrets.json"]:
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                pass
    return {}


@app.post("/api/sheet/sync")
async def sheet_sync(request: Request):
    """Manually trigger a sheet queue poll."""
    body = await request.json()
    sheet_id = body.get("sheet_id") or _load_secrets().get("socializer", {}).get("sheetId", "")
    if not sheet_id:
        raise HTTPException(400, "sheet_id required (or set socializer.sheetId in secrets.json)")
    import sys
    result = subprocess.Popen(
        [sys.executable, str(BASE / "scripts/sheet_queue.py"), "--sheet-id", sheet_id],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return {"ok": True, "message": "Sheet sync started", "pid": result.pid}


@app.get("/api/sheet/template")
async def sheet_template():
    """Return the expected Google Sheet column structure."""
    return {
        "columns": [
            {"col": "A", "name": "Client ID", "example": "mic-mann"},
            {"col": "B", "name": "Platforms", "example": "x,linkedin"},
            {"col": "C", "name": "Video Drive URL", "example": "https://drive.google.com/file/d/..."},
            {"col": "D", "name": "Caption - X", "example": "Post text for X (max 280 chars)"},
            {"col": "E", "name": "Caption - LinkedIn", "example": "Post text for LinkedIn"},
            {"col": "F", "name": "Caption - Instagram", "example": "Post text for Instagram"},
            {"col": "G", "name": "Caption - TikTok", "example": "Post text for TikTok"},
            {"col": "H", "name": "Schedule Date", "example": "2026-03-15 09:00 or now"},
            {"col": "I", "name": "Status", "example": "pending"},
            {"col": "J", "name": "Error", "example": ""},
            {"col": "K", "name": "Postiz Post ID", "example": ""},
            {"col": "L", "name": "Posted At", "example": ""},
        ],
        "instructions": [
            "Row 1 must be headers",
            "Set Status = 'pending' to queue a post",
            "Client ID must match a config in clients/ directory",
            "Drive URL must be a shared Google Drive link (anyone with link can view)",
            "Schedule Date format: YYYY-MM-DD HH:MM (Africa/Johannesburg timezone)",
            "Share the sheet with ai@mannmade.co.za (Editor access)",
        ]
    }


# ===== POST LOG ENDPOINTS =====

@app.get("/api/posts/log")
async def post_log(client_id: str = "", limit: int = 100):
    from publisher import get_post_log
    return {"posts": get_post_log(client_id, limit)}


@app.get("/api/posts/failed")
async def failed_posts(client_id: str = ""):
    from publisher import get_failed_posts
    return {"posts": get_failed_posts(client_id)}


@app.post("/api/posts/retry/{log_id}")
async def retry_post(log_id: int):
    """Manually trigger retry of a failed post."""
    from publisher import get_db, publish, PostStatus
    db = get_db()
    row = db.execute("SELECT * FROM post_log WHERE id=?", (log_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Post not found")
    row = dict(row)
    api_key = os.environ.get("POSTIZ_API_KEY", "")
    result = await publish(
        client_id=row["client_id"],
        platform=row["platform"],
        content=row["content"],
        media_path=row.get("media_path", ""),
        api_key=api_key
    )
    return result


# ===== APPROVAL WORKFLOW =====

@app.get("/api/posts/pending")
async def get_pending_posts():
    posts = load_queue()
    pending = [p for p in posts if p.get("status") == "pending_approval"]
    return pending


@app.post("/api/posts/{post_id}/approve")
async def approve_post(post_id: str):
    posts = load_queue()
    for p in posts:
        if p["id"] == post_id:
            p["status"] = "scheduled"
            p["rejection_reason"] = None
            save_queue(posts)
            return {"ok": True, "post": p}
    raise HTTPException(404, "Post not found")


@app.post("/api/posts/{post_id}/reject")
async def reject_post(post_id: str, request: Request):
    body = await request.json()
    reason = body.get("reason", "")
    posts = load_queue()
    for p in posts:
        if p["id"] == post_id:
            p["status"] = "rejected"
            p["rejection_reason"] = reason
            save_queue(posts)
            return {"ok": True, "post": p}
    raise HTTPException(404, "Post not found")


# ===== WEEKLY CALENDAR =====

@app.get("/api/posts/calendar")
async def posts_calendar(start: str = "", end: str = ""):
    posts = load_queue()
    scheduled = [p for p in posts if p.get("status") in ("scheduled", "posted", "pending_approval")]
    if start:
        try:
            start_dt = datetime.fromisoformat(start)
            scheduled = [p for p in scheduled if p.get("scheduled_at") and datetime.fromisoformat(p["scheduled_at"]) >= start_dt]
        except Exception:
            pass
    if end:
        try:
            end_dt = datetime.fromisoformat(end)
            scheduled = [p for p in scheduled if p.get("scheduled_at") and datetime.fromisoformat(p["scheduled_at"]) <= end_dt]
        except Exception:
            pass
    return scheduled


@app.patch("/api/posts/{post_id}/reschedule")
async def reschedule_post(post_id: str, request: Request):
    body = await request.json()
    new_time = body.get("scheduled_at", "")
    if not new_time:
        raise HTTPException(400, "scheduled_at required")
    posts = load_queue()
    for p in posts:
        if p["id"] == post_id:
            p["scheduled_at"] = new_time
            if p["status"] == "draft":
                p["status"] = "scheduled"
            save_queue(posts)
            return {"ok": True, "post": p}
    raise HTTPException(404, "Post not found")


# ===== PER-POST ANALYTICS =====

def _get_analytics_db():
    db_path = BASE / "data" / "post_log.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = __import__("sqlite3").connect(str(db_path))
    db.row_factory = __import__("sqlite3").Row
    # Ensure columns exist
    for col, coltype in [("likes", "INTEGER DEFAULT 0"), ("reposts", "INTEGER DEFAULT 0"), ("comments", "INTEGER DEFAULT 0")]:
        try:
            db.execute(f"ALTER TABLE post_log ADD COLUMN {col} {coltype}")
            db.commit()
        except Exception:
            pass
    return db


@app.get("/api/posts/{post_id}/detail")
async def post_detail(post_id: str):
    # Try to parse as integer (post_log ID)
    try:
        log_id = int(post_id)
    except ValueError:
        raise HTTPException(400, "post_id must be integer for detail view")

    db = _get_analytics_db()
    row = db.execute("SELECT * FROM post_log WHERE id=?", (log_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Post not found")
    post = dict(row)

    # Fetch retry history
    retries = db.execute(
        "SELECT * FROM retry_queue WHERE post_log_id=? ORDER BY retry_at DESC",
        (log_id,)
    ).fetchall()
    post["retry_history"] = [dict(r) for r in retries]
    return post


@app.patch("/api/posts/{post_id}/engagement")
async def update_engagement(post_id: str, request: Request):
    try:
        log_id = int(post_id)
    except ValueError:
        raise HTTPException(400, "post_id must be integer")

    body = await request.json()
    likes = int(body.get("likes", 0))
    reposts = int(body.get("reposts", 0))
    comments = int(body.get("comments", 0))

    db = _get_analytics_db()
    db.execute(
        "UPDATE post_log SET likes=?, reposts=?, comments=?, updated_at=datetime('now') WHERE id=?",
        (likes, reposts, comments, log_id)
    )
    db.commit()

    # Auto-save hook if total engagement >= 50
    total = likes + reposts + comments
    if total >= 50:
        row = db.execute("SELECT * FROM post_log WHERE id=?", (log_id,)).fetchone()
        if row:
            row = dict(row)
            words = (row.get("content") or "").split()[:10]
            hook_text = " ".join(words)
            if hook_text:
                hooks = _load_hooks()
                # Check if not already in library
                existing = [h for h in hooks if h.get("text", "").startswith(hook_text[:30])]
                if not existing:
                    import uuid as _uuid
                    hook = {
                        "id": str(_uuid.uuid4())[:8],
                        "text": hook_text,
                        "platform": row.get("platform", ""),
                        "engagement_score": total,
                        "date_used": row.get("created_at", ""),
                        "client": row.get("client_id", "")
                    }
                    hooks.append(hook)
                    _save_hooks(hooks)

    return {"ok": True, "likes": likes, "reposts": reposts, "comments": comments}


# ===== HASHTAG MANAGER =====

HASHTAG_SETS_FILE = BASE / "data" / "hashtag_sets.json"

DEFAULT_HASHTAG_SETS = [
    {"id": "ai-tech-sa", "name": "AI & Tech SA", "tags": ["#AI", "#TechSA", "#ArtificialIntelligence", "#SouthAfricaTech", "#FutureTech"], "platforms": ["x", "linkedin"]},
    {"id": "singularity-sa", "name": "Singularity SA", "tags": ["#SingularitySA", "#SUSA", "#ExponentialTech", "#FutureAfrica", "#Singularity"], "platforms": ["x", "linkedin", "instagram"]},
    {"id": "podpal", "name": "PodPal", "tags": ["#PodPal", "#Podcasting", "#PodcastGrowth", "#SouthAfricaPodcast", "#ContentCreator"], "platforms": ["x", "linkedin", "tiktok"]},
    {"id": "mann-made", "name": "Mann Made", "tags": ["#MannMade", "#AIVideo", "#CreativeAgency", "#SouthAfrica", "#VideoProduction"], "platforms": ["x", "linkedin", "instagram", "tiktok"]},
    {"id": "the-exponentials", "name": "The Exponentials", "tags": ["#TheExponentials", "#Exponential", "#AIAfrica", "#TechAfrica", "#Innovation"], "platforms": ["x", "linkedin", "tiktok", "youtube"]},
]


def _load_hashtag_sets() -> list:
    if not HASHTAG_SETS_FILE.exists():
        HASHTAG_SETS_FILE.parent.mkdir(parents=True, exist_ok=True)
        HASHTAG_SETS_FILE.write_text(json.dumps(DEFAULT_HASHTAG_SETS, indent=2))
    return json.loads(HASHTAG_SETS_FILE.read_text())


def _save_hashtag_sets(sets: list):
    HASHTAG_SETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    HASHTAG_SETS_FILE.write_text(json.dumps(sets, indent=2))


@app.get("/api/hashtags")
async def get_hashtags():
    return _load_hashtag_sets()


@app.post("/api/hashtags")
async def create_hashtag_set(request: Request):
    body = await request.json()
    sets = _load_hashtag_sets()
    if not body.get("id"):
        body["id"] = str(uuid.uuid4())[:8]
    sets.append(body)
    _save_hashtag_sets(sets)
    return body


@app.put("/api/hashtags/{set_id}")
async def update_hashtag_set(set_id: str, request: Request):
    body = await request.json()
    sets = _load_hashtag_sets()
    for i, s in enumerate(sets):
        if s["id"] == set_id:
            body["id"] = set_id
            sets[i] = body
            _save_hashtag_sets(sets)
            return body
    raise HTTPException(404, "Hashtag set not found")


@app.delete("/api/hashtags/{set_id}")
async def delete_hashtag_set(set_id: str):
    sets = _load_hashtag_sets()
    new_sets = [s for s in sets if s["id"] != set_id]
    if len(new_sets) == len(sets):
        raise HTTPException(404, "Hashtag set not found")
    _save_hashtag_sets(new_sets)
    return {"ok": True}


# ===== LARRY CREATIVE INTELLIGENCE =====

HOOK_LIBRARY_FILE = BASE / "data" / "hook_library.json"

LARRY_SYSTEM_PROMPT = """You are Larry, a senior social media strategist for Mann Made, a South African digital agency. You create content that sounds human, specific, and relevant - not corporate or AI-generated. Rules: no em dashes, no AI buzzwords (delve, tapestry, vibrant, leverage, transformative), no sycophancy, no rule-of-three patterns. Write like a smart person talking to their industry, not a brand announcement. Be specific. Have opinions. South African context where relevant."""


def _load_hooks() -> list:
    if not HOOK_LIBRARY_FILE.exists():
        HOOK_LIBRARY_FILE.parent.mkdir(parents=True, exist_ok=True)
        HOOK_LIBRARY_FILE.write_text("[]")
    return json.loads(HOOK_LIBRARY_FILE.read_text())


def _save_hooks(hooks: list):
    HOOK_LIBRARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HOOK_LIBRARY_FILE.write_text(json.dumps(hooks, indent=2))


def _get_anthropic_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        for path in [Path.home() / ".openclaw/secrets.json", BASE / "secrets.json"]:
            if path.exists():
                try:
                    data = json.loads(path.read_text())
                    key = data.get("anthropic", {}).get("apiKey", "")
                    if key:
                        break
                except Exception:
                    pass
    return key


LARRY_TEMPLATES = {
    "thought_leadership": {
        "x": "Here's something most {industry} people get wrong: {topic}. The real issue? {insight}. What's your take?",
        "linkedin": "{topic} - this is something the industry keeps getting backwards.\n\nHere's what I've noticed after working with clients across South Africa: {insight}\n\nThe data backs it up. {evidence}\n\nWhat's holding most people back isn't {common_excuse} - it's {real_reason}.\n\nThoughts?",
        "instagram": "Unpopular opinion: {topic}\n\n{insight}\n\nSave this if it changes how you think about {industry}.",
        "tiktok": "Nobody talks about this in {industry}: {topic}"
    },
    "product_promo": {
        "x": "We built {topic} for one reason: {reason}. If you've ever struggled with {problem}, this is for you.",
        "linkedin": "After months of work, {topic} is ready.\n\nWe built it because {reason}.\n\nThe problem it solves: {problem}\n\nHow it works: {how}\n\nIf this sounds relevant to your work, let's talk.",
        "instagram": "{topic} is live. Here's why we built it: {reason}",
        "tiktok": "We built {topic} and it solves {problem}"
    },
    "event_announcement": {
        "x": "{topic} is happening {date}. Here's what you'll get out of it: {value}. Limited spots.",
        "linkedin": "{topic} - mark your calendar.\n\nDate: {date}\nWhat it is: {description}\nWhy come: {value}\n\nRegistration link in bio.",
        "instagram": "{topic} is coming. {date}. You don't want to miss this.",
        "tiktok": "{topic} event - {date}. Here's what's happening:"
    },
    "engagement_hook": {
        "x": "Quick question for {industry} people: {question}",
        "linkedin": "I've been thinking about {topic} a lot lately.\n\n{question}\n\nGenuinely curious what you think - especially if you've seen this play out differently.",
        "instagram": "{question}\n\nDrop your answer below.",
        "tiktok": "Tell me in the comments: {question}"
    },
    "behind_the_scenes": {
        "x": "Behind the scenes at {topic}: {insight}. This is what building actually looks like.",
        "linkedin": "Real talk about {topic}:\n\n{insight}\n\nMost people only see the polished version. Here's what it actually takes:\n\n{reality}\n\nBuilding in public because the process matters as much as the result.",
        "instagram": "Behind the scenes: {topic}. {insight}",
        "tiktok": "What {topic} actually looks like behind the scenes:"
    }
}


@app.post("/api/larry/generate")
async def larry_generate(request: Request):
    import httpx
    body = await request.json()
    topic = body.get("topic", "")
    client_name = body.get("client", "")
    platforms = body.get("platforms", ["x", "linkedin"])
    content_type = body.get("content_type", "thought_leadership")

    if not topic:
        raise HTTPException(400, "topic is required")

    api_key = _get_anthropic_key()

    platform_rules = {
        "x": "Write a punchy tweet under 280 characters. Lead with the hook. No filler. Single thought, clear opinion.",
        "linkedin": "Write a LinkedIn post of 150-300 words. No day/week openers. Start with the observation. Short paragraphs. End with a question or call to action.",
        "instagram": "Write an Instagram caption, 2-5 sentences. Visual and specific. 3-5 hashtags at the end.",
        "tiktok": "Write a TikTok caption, hook-first, max 3 sentences. Punchy. Make them want to watch."
    }

    variations = []

    if api_key:
        try:
            content_type_label = content_type.replace("_", " ").title()
            prompt = f"""Generate 3 distinct social media post variations for the following:

Topic/Brief: {topic}
Client: {client_name or "Mann Made"}
Content Type: {content_type_label}
Platforms: {', '.join(platforms)}

Platform rules:
{chr(10).join(f"- {p}: {platform_rules.get(p, 'Keep it concise and engaging.')}" for p in platforms)}

Return EXACTLY this JSON format (no markdown, no explanation):
{{
  "variations": [
    {{
      "platform": "{platforms[0]}",
      "content": "post content here",
      "hashtag_suggestions": ["#tag1", "#tag2"]
    }}
  ]
}}

Generate one variation per platform listed. Make each one distinct in angle and tone."""

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": "claude-haiku-4-5",
                        "max_tokens": 1500,
                        "system": LARRY_SYSTEM_PROMPT,
                        "messages": [{"role": "user", "content": prompt}]
                    }
                )
            if resp.status_code == 200:
                text = resp.json()["content"][0]["text"].strip()
                # Parse JSON from response
                import re
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    variations = parsed.get("variations", [])
        except Exception as e:
            pass  # Fall through to templates

    # Fallback to smart templates
    if not variations:
        ct_key = content_type.replace(" ", "_").lower()
        templates = LARRY_TEMPLATES.get(ct_key, LARRY_TEMPLATES.get("thought_leadership", {}))
        hashtag_map = {
            "x": ["#Innovation", "#SouthAfrica"],
            "linkedin": ["#Leadership", "#SouthAfrica", "#Business"],
            "instagram": ["#BehindTheScenes", "#MannMade", "#SouthAfrica"],
            "tiktok": ["#LearnOnTikTok", "#SouthAfrica"]
        }
        for platform in platforms:
            template = templates.get(platform, f"Sharing thoughts on {topic}. {'{insight}'}")
            content = template.replace("{topic}", topic).replace("{industry}", "our industry").replace(
                "{insight}", f"the real story with {topic}").replace("{question}", f"What do you think about {topic}?").replace(
                "{reason}", "we saw a gap").replace("{problem}", "the usual friction").replace(
                "{how}", "by keeping it simple").replace("{evidence}", "the numbers show it").replace(
                "{real_reason}", "execution").replace("{common_excuse}", "resources").replace(
                "{date}", "soon").replace("{description}", topic).replace("{value}", "practical insights").replace(
                "{reality}", "long hours and honest feedback").replace("{description}", topic)
            variations.append({
                "platform": platform,
                "content": content,
                "hashtag_suggestions": hashtag_map.get(platform, ["#SouthAfrica"])
            })

    return {"variations": variations, "topic": topic, "content_type": content_type}


@app.get("/api/larry/insights")
async def larry_insights():
    db = _get_analytics_db()

    try:
        rows = db.execute(
            "SELECT *, (COALESCE(likes,0)+COALESCE(reposts,0)+COALESCE(comments,0)) as total_engagement FROM post_log WHERE (COALESCE(likes,0)+COALESCE(reposts,0)+COALESCE(comments,0)) > 0 ORDER BY total_engagement DESC"
        ).fetchall()
    except Exception:
        return {"topPosts": [], "bottomPosts": [], "bestPlatform": None, "bestDayOfWeek": None, "bestHour": None, "hookPatterns": {}, "recommendations": ["Start tracking engagement to see insights here."]}

    posts = [dict(r) for r in rows]

    if not posts:
        return {
            "topPosts": [],
            "bottomPosts": [],
            "bestPlatform": None,
            "bestDayOfWeek": None,
            "bestHour": None,
            "hookPatterns": {"top": [], "bottom": []},
            "recommendations": ["No engagement data yet. Update post engagement to see insights."]
        }

    # By platform
    platform_eng = {}
    platform_count = {}
    for p in posts:
        pl = p.get("platform", "unknown")
        platform_eng[pl] = platform_eng.get(pl, 0) + p.get("total_engagement", 0)
        platform_count[pl] = platform_count.get(pl, 0) + 1
    platform_avg = {pl: platform_eng[pl] / platform_count[pl] for pl in platform_eng}
    best_platform = max(platform_avg, key=platform_avg.get) if platform_avg else None

    # By day of week
    day_eng = {}
    day_count = {}
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for p in posts:
        ca = p.get("created_at", "")
        if ca:
            try:
                dt = datetime.fromisoformat(ca)
                dow = dt.weekday()
                day_eng[dow] = day_eng.get(dow, 0) + p.get("total_engagement", 0)
                day_count[dow] = day_count.get(dow, 0) + 1
            except Exception:
                pass
    day_avg = {d: day_eng[d] / day_count[d] for d in day_eng}
    best_dow_idx = max(day_avg, key=day_avg.get) if day_avg else None
    best_day = days_of_week[best_dow_idx] if best_dow_idx is not None else None

    # By hour
    hour_eng = {}
    hour_count = {}
    for p in posts:
        ca = p.get("created_at", "")
        if ca:
            try:
                dt = datetime.fromisoformat(ca)
                h = dt.hour
                hour_eng[h] = hour_eng.get(h, 0) + p.get("total_engagement", 0)
                hour_count[h] = hour_count.get(h, 0) + 1
            except Exception:
                pass
    hour_avg = {h: hour_eng[h] / hour_count[h] for h in hour_eng}
    best_hour = max(hour_avg, key=hour_avg.get) if hour_avg else None

    # Hook patterns
    top_5 = posts[:5]
    bottom_5 = posts[-5:]
    top_hooks = [" ".join((p.get("content") or "").split()[:8]) for p in top_5]
    bottom_hooks = [" ".join((p.get("content") or "").split()[:8]) for p in bottom_5]

    # Recommendations
    recommendations = []
    if best_platform:
        recommendations.append(f"Post more on {best_platform} - it gets the highest engagement on average.")
    if best_day:
        recommendations.append(f"{best_day} is your best day for engagement. Schedule key posts for then.")
    if best_hour is not None:
        recommendations.append(f"Posts at {best_hour}:00 perform best. Aim for that window.")
    if not recommendations:
        recommendations = ["Keep posting consistently to build engagement data."]

    return {
        "topPosts": [{"id": p["id"], "content": (p.get("content") or "")[:120], "platform": p.get("platform"), "total_engagement": p.get("total_engagement", 0)} for p in top_5],
        "bottomPosts": [{"id": p["id"], "content": (p.get("content") or "")[:120], "platform": p.get("platform"), "total_engagement": p.get("total_engagement", 0)} for p in bottom_5],
        "bestPlatform": best_platform,
        "bestDayOfWeek": best_day,
        "bestHour": best_hour,
        "hookPatterns": {"top": top_hooks, "bottom": bottom_hooks},
        "recommendations": recommendations
    }


@app.get("/api/larry/hooks")
async def get_hooks():
    hooks = _load_hooks()
    hooks.sort(key=lambda h: h.get("engagement_score", 0), reverse=True)
    return hooks


@app.post("/api/larry/hooks")
async def save_hook(request: Request):
    body = await request.json()
    hooks = _load_hooks()
    hook = {
        "id": body.get("id") or str(uuid.uuid4())[:8],
        "text": body.get("text", ""),
        "platform": body.get("platform", ""),
        "engagement_score": int(body.get("engagement_score", 0)),
        "date_used": body.get("date_used", datetime.now().isoformat()),
        "client": body.get("client", "")
    }
    hooks.append(hook)
    _save_hooks(hooks)
    return hook


# Initialise hashtag sets on startup
_load_hashtag_sets()


# ===== LARRY BRAND DNA =====

BRAND_DNA_DIR = BASE / "data" / "brand_dna"
AD_TEMPLATES_FILE = BASE / "data" / "ad_templates.json"
GENERATED_IMAGES_DIR = BASE / "data" / "generated_images"


@app.post("/api/larry/brand-dna")
async def larry_brand_dna(request: Request):
    import httpx
    body = await request.json()
    client_id = body.get("client_id", "")
    url = body.get("url", "")
    if not url:
        raise HTTPException(400, "url is required")

    # Fetch URL content
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as hclient:
            r = await hclient.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; MannMade/1.0)"})
            html = r.text
    except Exception as e:
        raise HTTPException(400, f"Could not fetch URL: {e}")

    # Extract visible text
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = text[:8000]

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        raise HTTPException(503, "OPENAI_API_KEY not set")

    system_prompt = """Analyse this brand's website content and extract a Brand DNA document in JSON format with these fields:
{
  "brand_name": "",
  "tagline": "",
  "industry": "",
  "target_audience": "",
  "tone_of_voice": ["adjective1", "adjective2", "adjective3"],
  "key_messages": ["message1", "message2", "message3"],
  "visual_identity": {
    "primary_colors": ["#hex1", "#hex2"],
    "style": "description of visual aesthetic",
    "photography_style": "description"
  },
  "competitors": ["competitor1", "competitor2"],
  "content_themes": ["theme1", "theme2", "theme3", "theme4"],
  "avoid": ["things not to say or do for this brand"]
}
Return ONLY the JSON object, nothing else."""

    try:
        async with httpx.AsyncClient(timeout=30) as hclient:
            resp = await hclient.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "max_tokens": 1000,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Website content:\n\n{text}"}
                    ]
                }
            )
            resp.raise_for_status()
            content_text = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise HTTPException(500, f"OpenAI error: {e}")

    try:
        json_match = re.search(r'\{.*\}', content_text, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON in response")
        brand_dna = json.loads(json_match.group())
    except Exception as e:
        raise HTTPException(500, f"Failed to parse brand DNA: {e}")

    BRAND_DNA_DIR.mkdir(parents=True, exist_ok=True)
    if client_id:
        (BRAND_DNA_DIR / f"{client_id}.json").write_text(json.dumps(brand_dna, indent=2))
        try:
            cfg = load_client(client_id)
            cfg["brand_dna"] = brand_dna
            save_client(cfg)
        except Exception:
            pass

    return brand_dna


@app.get("/api/larry/brand-dna/{client_id}")
async def get_brand_dna(client_id: str):
    f = BRAND_DNA_DIR / f"{client_id}.json"
    if not f.exists():
        raise HTTPException(404, "No brand DNA found for this client")
    return json.loads(f.read_text())


# ===== LARRY IMAGE GENERATION =====

@app.post("/api/larry/generate-image")
async def larry_generate_image(request: Request):
    import httpx, base64
    body = await request.json()
    prompt = body.get("prompt", "")
    aspect_ratio = body.get("aspect_ratio", "portrait")

    if not prompt:
        raise HTTPException(400, "prompt is required")

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        raise HTTPException(503, "GEMINI_API_KEY not set")

    ar_map = {"square": "1:1", "portrait": "9:16", "landscape": "16:9"}
    ar = ar_map.get(aspect_ratio, "9:16")

    try:
        async with httpx.AsyncClient(timeout=60) as hclient:
            resp = await hclient.post(
                "https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict",
                headers={"x-goog-api-key": gemini_key, "Content-Type": "application/json"},
                json={
                    "instances": [{"prompt": prompt}],
                    "parameters": {"sampleCount": 1, "aspectRatio": ar}
                }
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        raise HTTPException(500, f"Gemini API error: {e}")

    try:
        predictions = data.get("predictions", [])
        if not predictions:
            raise ValueError("No predictions returned")
        img_b64 = predictions[0].get("bytesBase64Encoded", "")
        if not img_b64:
            raise ValueError("No image data in response")
        img_bytes = base64.b64decode(img_b64)
    except Exception as e:
        raise HTTPException(500, f"Image decode error: {e}")

    GENERATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4()}.png"
    (GENERATED_IMAGES_DIR / filename).write_bytes(img_bytes)

    return {"image_url": f"/api/larry/image/{filename}", "filename": filename}


@app.get("/api/larry/image/{filename}")
async def serve_generated_image(filename: str):
    safe = re.sub(r"[^a-zA-Z0-9._-]", "", filename)
    path = GENERATED_IMAGES_DIR / safe
    if not path.exists():
        raise HTTPException(404, "Image not found")
    return FileResponse(str(path), media_type="image/png")


# ===== LARRY AD TEMPLATES =====

@app.get("/api/larry/templates")
async def get_larry_templates():
    if AD_TEMPLATES_FILE.exists():
        return json.loads(AD_TEMPLATES_FILE.read_text())
    return []


@app.post("/api/larry/generate-from-template")
async def larry_generate_from_template(request: Request):
    import httpx
    body = await request.json()
    template_id = body.get("template_id", "")
    client_id = body.get("client_id", "")
    platform = body.get("platform", "x")

    if not template_id:
        raise HTTPException(400, "template_id is required")

    templates = json.loads(AD_TEMPLATES_FILE.read_text()) if AD_TEMPLATES_FILE.exists() else []
    template = next((t for t in templates if t["id"] == template_id), None)
    if not template:
        raise HTTPException(404, "Template not found")

    brand_dna = {}
    if client_id:
        dna_file = BRAND_DNA_DIR / f"{client_id}.json"
        if dna_file.exists():
            try:
                brand_dna = json.loads(dna_file.read_text())
            except Exception:
                pass

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        raise HTTPException(503, "OPENAI_API_KEY not set")

    platform_rules = {
        "x": "Max 280 chars. Hook-first. No filler.",
        "linkedin": "150-300 words. Start with observation. Short paragraphs. End with question.",
        "instagram": "2-5 sentences. Visual. 3-5 hashtags at end.",
        "tiktok": "Max 3 sentences. Punchy hook."
    }

    brand_context = ""
    if brand_dna:
        brand_context = f"\n\nBrand: {brand_dna.get('brand_name', '')}\nTone: {', '.join(brand_dna.get('tone_of_voice', []))}\nKey messages: {', '.join(brand_dna.get('key_messages', []))}\nAvoid: {', '.join(brand_dna.get('avoid', []))}"

    prompt = f"""Fill in this ad template for {platform}:

Template: {template['name']}
Structure:
{template['structure']}

Platform rules: {platform_rules.get(platform, 'Be concise and engaging.')}{brand_context}

Return ONLY the filled post text, nothing else. Follow the structure but make it natural and human. No em dashes."""

    try:
        async with httpx.AsyncClient(timeout=30) as hclient:
            resp = await hclient.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "max_tokens": 600,
                    "messages": [
                        {"role": "system", "content": "You are a social media copywriter. Write engaging, human-sounding content. No em dashes. No AI buzzwords like leverage, seamlessly, transformative, vibrant, delve, tapestry."},
                        {"role": "user", "content": prompt}
                    ]
                }
            )
            resp.raise_for_status()
            content_text = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise HTTPException(500, f"OpenAI error: {e}")

    return {
        "content": content_text,
        "template": template,
        "platform": platform,
        "client_id": client_id
    }


# ===== LARRY BATCH SCHEDULING =====

@app.post("/api/larry/batch-generate")
async def larry_batch_generate(request: Request):
    import httpx, sqlite3 as _sqlite3
    body = await request.json()
    client_id = body.get("client_id", "")
    platforms = body.get("platforms", ["x", "linkedin"])
    days = int(body.get("days", 7))
    posts_per_day = int(body.get("posts_per_day", 2))

    if not client_id:
        raise HTTPException(400, "client_id is required")
    if not platforms:
        raise HTTPException(400, "platforms list is required")
    if days < 1 or days > 14:
        raise HTTPException(400, "days must be 1-14")
    if posts_per_day < 1 or posts_per_day > 4:
        raise HTTPException(400, "posts_per_day must be 1-4")

    cfg = load_client(client_id)

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        raise HTTPException(503, "OPENAI_API_KEY not set")

    brand_dna = {}
    dna_file = BRAND_DNA_DIR / f"{client_id}.json"
    if dna_file.exists():
        try:
            brand_dna = json.loads(dna_file.read_text())
        except Exception:
            pass

    platform_prompts = {
        "x": "Write one punchy X (Twitter) post under 280 characters. Hook-first. Opinionated. No hashtag spam. No filler.",
        "linkedin": "Write one LinkedIn post 150-250 words. Narrative style. Start with a specific observation, not 'I' or 'In today'. Professional but not stiff.",
        "instagram": "Write an Instagram caption 2-5 sentences. Visual and specific. 3-5 relevant hashtags at end.",
        "tiktok": "Write a TikTok caption under 3 sentences. Punchy hook first."
    }

    system_prompt = """You are writing social media posts for a brand. Rules:
- No em dashes (use hyphens or commas instead)
- No AI buzzwords: leverage, seamlessly, transformative, vibrant, delve, tapestry, robust, comprehensive, groundbreaking
- No sycophancy, no 'exciting times', no corporate speak
- Be specific with facts or numbers when possible
- Sound human and direct
Return ONLY the post text, nothing else."""

    now = datetime.now()
    generated_posts = []
    by_platform = {p: 0 for p in platforms}

    db_path = BASE / "data" / "socializer.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, client TEXT, platform TEXT,
        content TEXT, status TEXT, postiz_id TEXT, error TEXT,
        created_at TEXT, posted_at TEXT, scheduled_at TEXT)""")
    try:
        conn.execute("ALTER TABLE posts ADD COLUMN scheduled_at TEXT")
    except Exception:
        pass
    conn.commit()

    postiz_api_key = _postiz_api_key()
    postiz_base = _postiz_base_url()

    async with httpx.AsyncClient(timeout=30) as hclient:
        for day_offset in range(days):
            target_date = now + timedelta(days=day_offset + 1)

            for platform in platforms:
                platform_cfg = cfg.get("platforms", {}).get(platform, {})
                post_times = platform_cfg.get("post_times", ["09:00", "17:00"])
                postiz_integration_id = platform_cfg.get("postiz_integration_id", "")

                # Select times for this day (spread to posts_per_day)
                selected_times = post_times[:posts_per_day]
                while len(selected_times) < posts_per_day:
                    hour = 9 + len(selected_times) * (8 // max(posts_per_day, 1))
                    selected_times.append(f"{hour % 24:02d}:00")

                for i, time_str in enumerate(selected_times[:posts_per_day]):
                    try:
                        h, m = map(int, time_str.split(":"))
                    except Exception:
                        h, m = 9, 0

                    scheduled_dt = target_date.replace(hour=h, minute=m, second=0, microsecond=0)
                    scheduled_iso = scheduled_dt.isoformat()

                    brand_context = ""
                    if brand_dna:
                        brand_context = f"\n\nBrand: {brand_dna.get('brand_name', client_id)}\nTone: {', '.join(brand_dna.get('tone_of_voice', []))}\nThemes: {', '.join(brand_dna.get('content_themes', []))}"

                    slot = "morning" if h < 12 else ("afternoon" if h < 17 else "evening")
                    user_msg = f"{platform_prompts.get(platform, 'Write a social post.')}{brand_context}\n\nPost {i + 1} of {posts_per_day} for {target_date.strftime('%A %B %d')} at {time_str} ({slot}). Make it fresh."

                    try:
                        resp = await hclient.post(
                            "https://api.openai.com/v1/chat/completions",
                            headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                            json={
                                "model": "gpt-4o-mini",
                                "max_tokens": 500,
                                "messages": [
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": user_msg}
                                ]
                            }
                        )
                        resp.raise_for_status()
                        content_text = resp.json()["choices"][0]["message"]["content"].strip()
                    except Exception as e:
                        content_text = f"[Generation failed: {e}]"

                    postiz_id = None
                    status = "scheduled"
                    if postiz_integration_id and postiz_api_key:
                        try:
                            postiz_headers = {"Authorization": f"Bearer {postiz_api_key}", "Content-Type": "application/json"}
                            pr = await hclient.post(
                                f"{postiz_base}/api/posts",
                                headers=postiz_headers,
                                json={
                                    "content": content_text,
                                    "integrations": [postiz_integration_id],
                                    "scheduleDate": scheduled_iso
                                }
                            )
                            pr.raise_for_status()
                            pr_data = pr.json()
                            postiz_id = str(pr_data.get("id", ""))
                        except Exception:
                            pass

                    conn.execute(
                        "INSERT INTO posts (client,platform,content,status,postiz_id,created_at,scheduled_at) VALUES (?,?,?,?,?,?,?)",
                        (client_id, platform, content_text, status, postiz_id,
                         datetime.utcnow().isoformat(), scheduled_iso)
                    )
                    conn.commit()

                    generated_posts.append({
                        "platform": platform,
                        "content_preview": content_text[:60],
                        "scheduled_at": scheduled_iso,
                        "postiz_id": postiz_id
                    })
                    by_platform[platform] = by_platform.get(platform, 0) + 1

    conn.close()

    return {
        "total": len(generated_posts),
        "by_platform": by_platform,
        "posts": generated_posts
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CLIPPINGS — AI video clip generation
# ═══════════════════════════════════════════════════════════════════════════════

CLIPS_DIR        = BASE / "data" / "clips"
CLIPS_UPLOADS    = CLIPS_DIR / "uploads"
CLIPS_OUTPUT     = CLIPS_DIR / "output"
CLIPS_JOBS       = CLIPS_DIR / "jobs"

for _d in [CLIPS_UPLOADS, CLIPS_OUTPUT, CLIPS_JOBS]:
    _d.mkdir(parents=True, exist_ok=True)


def _clips_get_job(job_id: str) -> dict:
    path = CLIPS_JOBS / f"{job_id}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _clips_save_job(job_id: str, state: dict):
    (CLIPS_JOBS / f"{job_id}.json").write_text(json.dumps(state, indent=2))


def _clips_run_job(job_id: str, video_path: str, num_clips: int, anthropic_key: str):
    """Blocking clip generation — called from a thread pool executor."""
    output_dir = str(CLIPS_OUTPUT)
    state = _clips_get_job(job_id)
    try:
        state["status"] = "transcribing"
        _clips_save_job(job_id, state)

        def _progress(msg: str):
            st = _clips_get_job(job_id)
            st["progress"] = msg
            if "transcrib" in msg.lower():
                st["status"] = "transcribing"
            elif "finding" in msg.lower() or "ai" in msg.lower():
                st["status"] = "detecting"
            elif "cutting" in msg.lower() or "clip" in msg.lower():
                st["status"] = "cutting"
            _clips_save_job(job_id, st)

        clips = _clipper_process_video(
            video_path=video_path,
            output_dir=output_dir,
            num_clips=num_clips,
            anthropic_key=anthropic_key or None,
            progress_callback=_progress,
        )

        # Enrich with metadata
        enriched = []
        for c in clips:
            clip_path = Path(c["clip_path"])
            stat = clip_path.stat() if clip_path.exists() else None
            enriched.append({
                **c,
                "id": clip_path.stem,
                "filename": clip_path.name,
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat() if stat else datetime.now().isoformat(),
            })

        state["status"] = "done"
        state["clips"] = enriched
        state["progress"] = f"Done! Generated {len(enriched)} clips."
        _clips_save_job(job_id, state)

    except Exception as e:
        state["status"] = "error"
        state["error"] = str(e)
        _clips_save_job(job_id, state)


@app.post("/api/clips/process")
async def clips_process(
    request: Request,
    file: UploadFile = File(None),
):
    if not _clipper_ok:
        raise HTTPException(503, "Clipper engine not available")

    job_id = str(uuid.uuid4())
    num_clips = 5
    anthropic_key = _get_anthropic_key()

    if file and file.filename:
        # File upload
        safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", file.filename)
        upload_path = CLIPS_UPLOADS / f"{job_id}_{safe_name}"
        with open(upload_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        video_path = str(upload_path)
    else:
        # JSON body with local path
        body = await request.json()
        video_path = body.get("video_path", "")
        num_clips = int(body.get("num_clips", 5))
        if not video_path or not Path(video_path).exists():
            raise HTTPException(400, "video_path not found")

    state = {
        "job_id": job_id,
        "status": "queued",
        "video_path": video_path,
        "num_clips": num_clips,
        "clips": [],
        "error": None,
        "progress": "Queued",
        "created_at": datetime.now().isoformat(),
    }
    _clips_save_job(job_id, state)

    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        None,
        _clips_run_job,
        job_id,
        video_path,
        num_clips,
        anthropic_key,
    )

    return {"job_id": job_id}


@app.get("/api/clips/job/{job_id}")
async def clips_job_status(job_id: str):
    state = _clips_get_job(job_id)
    if not state:
        raise HTTPException(404, "Job not found")
    return state


@app.get("/api/clips/")
async def clips_list():
    clips = []
    for f in sorted(CLIPS_OUTPUT.glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True):
        stat = f.stat()
        # Try to load metadata from matching job
        meta = {"score": None, "reason": "", "title": f.stem}
        for job_file in CLIPS_JOBS.glob("*.json"):
            try:
                job = json.loads(job_file.read_text())
                for c in job.get("clips", []):
                    if c.get("filename") == f.name:
                        meta = c
                        break
            except Exception:
                pass

        clips.append({
            "id": f.stem,
            "title": meta.get("title", f.stem),
            "filename": f.name,
            "score": meta.get("score"),
            "reason": meta.get("reason", ""),
            "transcript_excerpt": meta.get("transcript_excerpt", ""),
            "start": meta.get("start"),
            "end": meta.get("end"),
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "size_mb": round(stat.st_size / 1024 / 1024, 1),
        })
    return clips


@app.get("/api/clips/file/{filename}")
async def clips_file(filename: str):
    """Serve a clip file for in-browser preview/download."""
    safe = re.sub(r"[^a-zA-Z0-9._-]", "", filename)
    path = CLIPS_OUTPUT / safe
    if not path.exists():
        raise HTTPException(404, "Clip not found")
    return FileResponse(str(path), media_type="video/mp4")


@app.delete("/api/clips/{clip_id}")
async def clips_delete(clip_id: str):
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", clip_id)
    # Find matching file
    matches = list(CLIPS_OUTPUT.glob(f"{safe_id}*.mp4"))
    if not matches:
        raise HTTPException(404, "Clip not found")
    for f in matches:
        f.unlink(missing_ok=True)
    return {"deleted": safe_id}


@app.post("/api/clips/{clip_id}/queue")
async def clips_add_to_queue(clip_id: str, request: Request):
    """Add a clip to the video post queue."""
    body = await request.json()
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", clip_id)
    matches = list(CLIPS_OUTPUT.glob(f"{safe_id}*.mp4"))
    if not matches:
        raise HTTPException(404, "Clip not found")
    clip_file = matches[0]

    # Build a video queue entry (same structure as existing video_queue.json)
    entry = {
        "id": str(uuid.uuid4())[:8],
        "clip_id": clip_id,
        "filename": clip_file.name,
        "filepath": str(clip_file),
        "client_id": body.get("client_id", ""),
        "platform": body.get("platform", ""),
        "scheduled_at": body.get("scheduled_at", ""),
        "caption": body.get("caption", ""),
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "type": "clip",
    }

    # Append to video_queue.json
    try:
        queue = json.loads(VIDEO_QUEUE_FILE.read_text()) if VIDEO_QUEUE_FILE.exists() else []
    except Exception:
        queue = []
    queue.append(entry)
    VIDEO_QUEUE_FILE.write_text(json.dumps(queue, indent=2))

    return entry


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7070)


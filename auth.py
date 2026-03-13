"""auth.py - JWT + bcrypt authentication for Mann Made Socializer"""
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from fastapi import Request, HTTPException, Depends
from fastapi.responses import RedirectResponse

BASE = Path(__file__).parent
USERS_FILE = BASE / "data" / "users.json"
SECRETS_FILE = BASE / "secrets.json"

SESSION_HOURS = 8
ALGORITHM = "HS256"

ROLE_HIERARCHY = {"admin": 3, "editor": 2, "viewer": 1}

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _load_secrets() -> dict:
    if SECRETS_FILE.exists():
        try:
            return json.loads(SECRETS_FILE.read_text())
        except Exception:
            pass
    return {}


def get_jwt_secret() -> str:
    s = _load_secrets()
    return s.get("socializer", {}).get("jwtSecret", "fallback-change-me-in-secrets.json")


# ---------------------------------------------------------------------------
# User store
# ---------------------------------------------------------------------------

def load_users() -> list:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text())
        except Exception:
            pass
    return []


def save_users(users: list):
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, indent=2))


def find_user(email: str) -> Optional[dict]:
    for u in load_users():
        if u.get("email", "").lower() == email.lower():
            return u
    return None


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def create_token(user: dict) -> str:
    payload = {
        "sub": user["email"],
        "name": user.get("name", ""),
        "role": user.get("role", "viewer"),
        "exp": datetime.utcnow() + timedelta(hours=SESSION_HOURS),
        "iat": datetime.utcnow(),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, get_jwt_secret(), algorithms=[ALGORITHM])
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# Request helpers
# ---------------------------------------------------------------------------

def get_token_from_request(request: Request) -> Optional[str]:
    # Cookie first, then Authorization header
    token = request.cookies.get("mm_auth")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    return token or None


def get_current_user(request: Request) -> Optional[dict]:
    token = get_token_from_request(request)
    if not token:
        return None
    return decode_token(token)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def require_auth(request: Request) -> dict:
    """FastAPI dependency: require valid JWT. Returns decoded payload."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_role(*roles: str):
    """FastAPI dependency factory: require one of the given roles."""
    def dependency(request: Request) -> dict:
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail=f"Role required: {', '.join(roles)}")
        return user
    return dependency


def require_admin(request: Request) -> dict:
    return require_role("admin")(request)


def require_editor_or_above(request: Request) -> dict:
    return require_role("admin", "editor")(request)


# ---------------------------------------------------------------------------
# Auth API route handlers (called from server.py)
# ---------------------------------------------------------------------------

async def handle_login(request: Request):
    from fastapi.responses import JSONResponse
    body = await request.json()
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""

    user = find_user(email)
    if not user or not user.get("active", True):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(user)
    resp = JSONResponse({
        "ok": True,
        "user": {
            "email": user["email"],
            "name": user.get("name", ""),
            "role": user.get("role", "viewer"),
        }
    })
    resp.set_cookie(
        key="mm_auth",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_HOURS * 3600,
        path="/",
    )
    return resp


async def handle_logout(request: Request):
    from fastapi.responses import JSONResponse
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("mm_auth", path="/")
    return resp


async def handle_me(request: Request):
    from fastapi.responses import JSONResponse
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return JSONResponse({
        "email": user["sub"],
        "name": user.get("name", ""),
        "role": user.get("role", "viewer"),
    })


# ---------------------------------------------------------------------------
# User management handlers (admin only)
# ---------------------------------------------------------------------------

async def handle_list_users(request: Request):
    from fastapi.responses import JSONResponse
    require_admin(request)
    users = load_users()
    safe = [
        {k: v for k, v in u.items() if k != "password_hash"}
        for u in users
    ]
    return JSONResponse(safe)


async def handle_create_user(request: Request):
    from fastapi.responses import JSONResponse
    require_admin(request)
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(400, "email is required")
    if find_user(email):
        raise HTTPException(409, f"User '{email}' already exists")
    role = body.get("role", "viewer")
    if role not in ROLE_HIERARCHY:
        raise HTTPException(400, f"Invalid role. Choose from: {', '.join(ROLE_HIERARCHY)}")
    password = body.get("password") or ""
    if len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    new_user = {
        "id": str(uuid.uuid4())[:8],
        "name": body.get("name", ""),
        "email": email,
        "password_hash": hash_password(password),
        "role": role,
        "created_at": datetime.utcnow().isoformat(),
        "active": True,
    }
    users = load_users()
    users.append(new_user)
    save_users(users)
    safe = {k: v for k, v in new_user.items() if k != "password_hash"}
    return JSONResponse(safe, status_code=201)


async def handle_delete_user(request: Request, email: str):
    from fastapi.responses import JSONResponse
    admin = require_admin(request)
    # Prevent self-deletion
    if admin["sub"].lower() == email.lower():
        raise HTTPException(400, "Cannot delete your own account")
    users = load_users()
    new_users = [u for u in users if u.get("email", "").lower() != email.lower()]
    if len(new_users) == len(users):
        raise HTTPException(404, f"User '{email}' not found")
    save_users(new_users)
    return JSONResponse({"ok": True})


async def handle_change_role(request: Request, email: str):
    from fastapi.responses import JSONResponse
    require_admin(request)
    body = await request.json()
    role = body.get("role", "")
    if role not in ROLE_HIERARCHY:
        raise HTTPException(400, f"Invalid role. Choose from: {', '.join(ROLE_HIERARCHY)}")
    users = load_users()
    for u in users:
        if u.get("email", "").lower() == email.lower():
            u["role"] = role
            save_users(users)
            return JSONResponse({"ok": True, "email": email, "role": role})
    raise HTTPException(404, f"User '{email}' not found")

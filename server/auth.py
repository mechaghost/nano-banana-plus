import os
import time
import secrets
from typing import Optional

import httpx
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

# In-memory OTP store: { email: { "code": str, "expires": float } }
_otp_store: dict[str, dict] = {}

_bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# API key CRUD (env var backed)
# ---------------------------------------------------------------------------

def _get_keys_set() -> set[str]:
    raw = os.environ.get("API_KEYS", "")
    return {k.strip() for k in raw.split(",") if k.strip()}


def _save_keys(keys: set[str]) -> None:
    os.environ["API_KEYS"] = ",".join(sorted(keys))


def generate_api_key(label: str = "") -> str:
    key = f"nbp_{secrets.token_urlsafe(32)}"
    keys = _get_keys_set()
    keys.add(key)
    _save_keys(keys)
    return key


def list_api_keys() -> list[dict]:
    return [{"key": k} for k in sorted(_get_keys_set())]


def revoke_api_key(key: str) -> bool:
    keys = _get_keys_set()
    if key not in keys:
        return False
    keys.discard(key)
    _save_keys(keys)
    return True


# ---------------------------------------------------------------------------
# OTP flow via Resend
# ---------------------------------------------------------------------------

async def request_otp(email: str) -> None:
    admin_email = os.environ.get("ADMIN_EMAIL", "")
    if not admin_email or email.lower() != admin_email.lower():
        return  # silent — prevents email enumeration

    code = f"{secrets.randbelow(1000000):06d}"
    _otp_store[email.lower()] = {
        "code": code,
        "expires": time.time() + 300,
    }

    resend_key = os.environ.get("RESEND_API_KEY", "")
    from_email = os.environ.get("RESEND_FROM_EMAIL", "noreply@example.com")
    if not resend_key:
        print(f"[AUTH] RESEND_API_KEY not set. OTP for {email}: {code}")
        return

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {resend_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": from_email,
                "to": [email],
                "subject": "Your login code",
                "text": f"Your OTP code is: {code}\n\nExpires in 5 minutes.",
            },
        )
        if resp.status_code >= 400:
            print(f"[AUTH] Resend API error: {resp.status_code} {resp.text}")


def verify_otp(email: str, code: str) -> Optional[str]:
    """Returns a JWT token string on success, None on failure."""
    entry = _otp_store.get(email.lower())
    if not entry:
        return None
    if time.time() > entry["expires"]:
        _otp_store.pop(email.lower(), None)
        return None
    if entry["code"] != code:
        return None

    _otp_store.pop(email.lower(), None)

    secret = os.environ.get("JWT_SECRET", "change-me-in-production")
    token = jwt.encode(
        {"sub": email.lower(), "exp": time.time() + JWT_EXPIRY_HOURS * 3600},
        secret,
        algorithm=JWT_ALGORITHM,
    )
    return token


# ---------------------------------------------------------------------------
# FastAPI auth dependency
# ---------------------------------------------------------------------------

async def require_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> str:
    """Returns an identity string. Raises 401 if unauthenticated."""
    # 1. Check X-API-Key header (AI agents)
    api_key = request.headers.get("X-API-Key")
    if api_key and api_key in _get_keys_set():
        return f"apikey:{api_key[:12]}..."

    # 2. Check JWT Bearer token (web UI)
    if credentials:
        try:
            secret = os.environ.get("JWT_SECRET", "change-me-in-production")
            payload = jwt.decode(credentials.credentials, secret, algorithms=[JWT_ALGORITHM])
            return f"user:{payload['sub']}"
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            pass

    raise HTTPException(status_code=401, detail="Authentication required")

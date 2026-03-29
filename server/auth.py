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
# Single API key (env var backed)
# ---------------------------------------------------------------------------

def get_api_key() -> str:
    """Return the API key, generating one if it doesn't exist."""
    key = os.environ.get("API_KEY", "")
    if not key:
        key = f"nbp_{secrets.token_urlsafe(32)}"
        os.environ["API_KEY"] = key
    return key


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
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header and api_key_header == get_api_key():
        return "apikey"

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

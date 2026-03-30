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
MAX_OTP_ATTEMPTS = 5

# In-memory OTP store: { email: { "code": str, "expires": float, "attempts": int } }
_otp_store: dict[str, dict] = {}

_bearer_scheme = HTTPBearer(auto_error=False)

# Fix #2: Generate a random JWT secret at startup if not set (prevents hardcoded fallback)
_jwt_secret = os.environ.get("JWT_SECRET", "") or secrets.token_urlsafe(32)


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
        "attempts": 0,
    }

    resend_key = os.environ.get("RESEND_API_KEY", "")
    from_email = os.environ.get("RESEND_FROM_EMAIL", "noreply@example.com")
    if not resend_key:
        # Fix #4: Don't log the OTP code itself
        print(f"[AUTH] RESEND_API_KEY not set — OTP email not sent for {email}")
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
            print(f"[AUTH] Resend API error: {resp.status_code}")


def verify_otp(email: str, code: str) -> Optional[str]:
    """Returns a JWT token string on success, None on failure."""
    entry = _otp_store.get(email.lower())
    if not entry:
        return None
    if time.time() > entry["expires"]:
        _otp_store.pop(email.lower(), None)
        return None
    # Fix #1: Lock out after MAX_OTP_ATTEMPTS
    if entry.get("attempts", 0) >= MAX_OTP_ATTEMPTS:
        _otp_store.pop(email.lower(), None)
        return None
    if entry["code"] != code:
        entry["attempts"] = entry.get("attempts", 0) + 1
        return None

    _otp_store.pop(email.lower(), None)

    token = jwt.encode(
        {"sub": email.lower(), "exp": int(time.time()) + JWT_EXPIRY_HOURS * 3600},
        _jwt_secret,
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
    # Fix #5: Constant-time comparison
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header and secrets.compare_digest(api_key_header, get_api_key()):
        return "apikey"

    # 2. Check JWT Bearer token (web UI)
    if credentials:
        try:
            payload = jwt.decode(credentials.credentials, _jwt_secret, algorithms=[JWT_ALGORITHM])
            return f"user:{payload['sub']}"
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            pass

    raise HTTPException(status_code=401, detail="Authentication required")

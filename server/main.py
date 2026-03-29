import os
import pathlib
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

from core import init_gemini_client, core_generate_image, core_process_image
import core
from auth import request_otp, verify_otp, require_auth, get_api_key

load_dotenv()

app = FastAPI(title="AI Image Generator & Processor API")

# CORS for local Vite dev server (not needed when serving same-origin in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:43210", "http://127.0.0.1:43210"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize on startup
init_gemini_client()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ConfigRequest(BaseModel):
    api_key: str = ""
    removebg_api_key: str = ""
    auto_save_dir: str = ""
    rate_limit_throttle: float = 4.0

class OTPRequest(BaseModel):
    email: str

class OTPVerifyRequest(BaseModel):
    email: str
    code: str


# ---------------------------------------------------------------------------
# Auth endpoints (public)
# ---------------------------------------------------------------------------

@app.post("/auth/request-otp")
async def auth_request_otp(body: OTPRequest):
    await request_otp(body.email)
    return {"status": "ok"}

@app.post("/auth/verify-otp")
async def auth_verify_otp(body: OTPVerifyRequest):
    token = verify_otp(body.email, body.code)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid or expired OTP")
    return {"token": token}


# ---------------------------------------------------------------------------
# Health (public)
# ---------------------------------------------------------------------------

@app.get("/api/v1/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/v1/info")
def api_info():
    """Public endpoint for AI agents to discover available API capabilities."""
    return {
        "name": "AI Image Studio",
        "version": "1.0.0",
        "auth": {
            "method": "API key",
            "header": "X-API-Key",
            "description": "Include your API key in the X-API-Key header on all /api/v1/* requests (except /health and /info).",
        },
        "endpoints": [
            {
                "method": "POST",
                "path": "/api/v1/generate",
                "description": "Generate an image from a text prompt using Google Imagen 4.0.",
                "content_type": "multipart/form-data",
                "parameters": {
                    "prompt": {"type": "string", "required": True, "description": "Text description of the image to generate."},
                    "model": {"type": "string", "required": False, "default": "imagen-4.0-fast-generate-001", "options": ["imagen-4.0-fast-generate-001", "imagen-4.0-fast-generate-001", "imagen-4.0-ultra-generate-001"]},
                    "aspect_ratio": {"type": "string", "required": False, "default": "1:1", "options": ["1:1", "3:4", "4:3", "9:16", "16:9"]},
                    "output_format": {"type": "string", "required": False, "default": "png", "options": ["png", "webp"]},
                    "output_resolution": {"type": "string", "required": False, "default": "", "description": "Set to '2K' for high resolution (Ultra model only)."},
                    "target_width": {"type": "integer", "required": False, "description": "Exact pixel width. Used with target_height for center-crop."},
                    "target_height": {"type": "integer", "required": False, "description": "Exact pixel height. Used with target_width for center-crop."},
                    "file": {"type": "file", "required": False, "description": "Optional base image for image-to-image generation."},
                },
                "response": "Image bytes with Content-Type image/png or image/webp.",
            },
            {
                "method": "POST",
                "path": "/api/v1/process",
                "description": "Remove the background from an image and trim to visible pixels.",
                "content_type": "multipart/form-data",
                "parameters": {
                    "file": {"type": "file", "required": True, "description": "The image to process."},
                    "output_format": {"type": "string", "required": False, "default": "png", "options": ["png", "webp"]},
                },
                "response": "Processed image bytes (transparent background) with Content-Type image/png or image/webp.",
            },
            {
                "method": "GET",
                "path": "/api/v1/health",
                "description": "Health check. No auth required.",
                "response": '{"status": "ok"}',
            },
        ],
    }


# ---------------------------------------------------------------------------
# Config (protected)
# ---------------------------------------------------------------------------

@app.get("/api/v1/config", dependencies=[Depends(require_auth)])
def get_config():
    api_key = os.environ.get("GEMINI_API_KEY", "")
    removebg_key = os.environ.get("REMOVEBG_API_KEY", "")
    auto_save_dir = os.environ.get("AUTO_SAVE_DIR", "")
    try:
        rate_limit_throttle = float(os.environ.get("RATE_LIMIT_DELAY", 4.0))
    except (ValueError, TypeError):
        rate_limit_throttle = 4.0
    has_key = bool(api_key and api_key != "your_api_key_here" and api_key.strip() != "")
    has_removebg_key = bool(removebg_key and removebg_key.strip() != "")
    return {
        "has_api_key": has_key,
        "has_removebg_key": has_removebg_key,
        "auto_save_dir": auto_save_dir,
        "rate_limit_throttle": rate_limit_throttle,
    }


@app.post("/api/v1/config", dependencies=[Depends(require_auth)])
def set_config(request: ConfigRequest):
    # Update current process environment
    if request.api_key:
        os.environ["GEMINI_API_KEY"] = request.api_key
    if request.removebg_api_key:
        os.environ["REMOVEBG_API_KEY"] = request.removebg_api_key
    os.environ["AUTO_SAVE_DIR"] = request.auto_save_dir
    os.environ["RATE_LIMIT_DELAY"] = str(request.rate_limit_throttle)

    # Only write .env file in local development (Railway filesystem is ephemeral)
    if not os.environ.get("RAILWAY_ENVIRONMENT"):
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        with open(env_path, 'w') as f:
            f.write(f'GEMINI_API_KEY="{os.environ.get("GEMINI_API_KEY", "")}"\n')
            f.write(f'REMOVEBG_API_KEY="{os.environ.get("REMOVEBG_API_KEY", "")}"\n')
            f.write(f'AUTO_SAVE_DIR="{request.auto_save_dir}"\n')
            f.write(f'RATE_LIMIT_DELAY="{request.rate_limit_throttle}"\n')
            # Preserve auth-related env vars across server reloads
            for key in ("ADMIN_EMAIL", "JWT_SECRET", "RESEND_API_KEY", "RESEND_FROM_EMAIL", "API_KEY"):
                val = os.environ.get(key, "")
                if val:
                    f.write(f'{key}="{val}"\n')

    init_gemini_client()
    return {"status": "success", "has_api_key": core.client is not None}


# ---------------------------------------------------------------------------
# API key (protected) — single key, read from env var
# ---------------------------------------------------------------------------

@app.get("/api/v1/api-key", dependencies=[Depends(require_auth)])
def get_api_key_endpoint():
    return {"key": get_api_key()}


# ---------------------------------------------------------------------------
# Image generation & processing (protected)
# ---------------------------------------------------------------------------

@app.post("/api/v1/generate", dependencies=[Depends(require_auth)])
async def generate_image(
    prompt: str = Form(...),
    model: str = Form("imagen-4.0-fast-generate-001"),
    aspect_ratio: str = Form("1:1"),
    output_resolution: str = Form(""),
    output_format: str = Form("png"),
    target_width: Optional[int] = Form(None),
    target_height: Optional[int] = Form(None),
    file: UploadFile = File(None)
):
    try:
        base_image_bytes = await file.read() if file else None
        image_bytes, media_type = await core_generate_image(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            output_resolution=output_resolution,
            output_format=output_format,
            target_width=target_width,
            target_height=target_height,
            base_image_bytes=base_image_bytes
        )
        return Response(content=image_bytes, media_type=media_type)
    except ValueError as ve:
        raise HTTPException(status_code=500, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/process", dependencies=[Depends(require_auth)])
async def process_image(
    file: UploadFile = File(...),
    output_format: str = Form("png")
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")
    try:
        contents = await file.read()
        final_bytes, media_type = await core_process_image(contents, output_format)
        return Response(content=final_bytes, media_type=media_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Serve built frontend in production (must be AFTER all API routes)
# ---------------------------------------------------------------------------

frontend_dist = pathlib.Path(__file__).parent.parent / "web" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 43211))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=os.environ.get("RAILWAY_ENVIRONMENT") is None)

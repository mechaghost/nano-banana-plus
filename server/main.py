import os
import io
import datetime
import time
import asyncio
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

from core import init_gemini_client, core_generate_image, core_process_image, client as core_client
import core

load_dotenv()

app = FastAPI(title="AI Image Generator & Processor API")

# Add CORS middleware to allow cross-origin requests from our Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:43210", "http://127.0.0.1:43210"], # Strictly restricted to local frontend instance
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini Client explicitly
init_gemini_client()

# Removed GenerateRequest model to support multipart/form-data.

class ConfigRequest(BaseModel):
    api_key: str
    auto_save_dir: str = ""
    rate_limit_throttle: float = 4.0

@app.get("/api/v1/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/v1/config")
def get_config():
    api_key = os.environ.get("GEMINI_API_KEY", "")
    auto_save_dir = os.environ.get("AUTO_SAVE_DIR", "")
    try:
        rate_limit_throttle = float(os.environ.get("RATE_LIMIT_DELAY", 4.0))
    except (ValueError, TypeError):
        rate_limit_throttle = 4.0
    has_key = bool(api_key and api_key != "your_api_key_here" and api_key.strip() != "")
    return {"has_api_key": has_key, "auto_save_dir": auto_save_dir, "rate_limit_throttle": rate_limit_throttle}

@app.post("/api/v1/config")
def set_config(request: ConfigRequest):
    # Save to .env file
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    
    # Simple write, overwriting the file
    with open(env_path, 'w') as f:
        f.write(f'GEMINI_API_KEY="{request.api_key}"\n')
        f.write(f'AUTO_SAVE_DIR="{request.auto_save_dir}"\n')
        f.write(f'RATE_LIMIT_DELAY="{request.rate_limit_throttle}"\n')
        
    # Update current process environment
    os.environ["GEMINI_API_KEY"] = request.api_key
    os.environ["AUTO_SAVE_DIR"] = request.auto_save_dir
    os.environ["RATE_LIMIT_DELAY"] = str(request.rate_limit_throttle)
    
    # Reinitialize client
    init_gemini_client()
    
    return {"status": "success", "has_api_key": core.client is not None}

@app.post("/api/v1/generate")
async def generate_image(
    prompt: str = Form(...),
    model: str = Form("imagen-4.0-generate-001"),
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

@app.post("/api/v1/process")
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=43211, reload=True)

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
from google import genai
from google.genai import types
from rembg import remove
from PIL import Image
from dotenv import load_dotenv

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

# Initialize Gemini Client lazily or from env.
client = None

def init_gemini_client():
    global client
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key and api_key != "your_api_key_here":
        try:
            client = genai.Client(api_key=api_key)
            print("Gemini client initialized successfully.")
        except Exception as e:
            print(f"Warning: Could not initialize Gemini Client. Error: {e}")
            client = None
    else:
        client = None

init_gemini_client()

# We will use Form and File parameters instead of a JSON BaseModel so we can accept images.
# Removed GenerateRequest model to support multipart/form-data.

class ConfigRequest(BaseModel):
    api_key: str
    auto_save_dir: str = ""
    rate_limit_throttle: float = 4.0

# Global rate limit queue for Gemini API
# Free Tier maxes out at 15 Requests Per Minute (1 every 4.0 seconds)
rate_limit_lock = asyncio.Lock()
last_request_time = 0.0

async def wait_for_rate_limit(min_delay_seconds: float = 4.0):
    global last_request_time
    async with rate_limit_lock:
        current_time = time.time()
        time_since_last = current_time - last_request_time
        if time_since_last < min_delay_seconds:
            delay = min_delay_seconds - time_since_last
            print(f"Rate limit queue: Holding request for {delay:.2f} seconds...")
            await asyncio.sleep(delay)
        last_request_time = time.time()

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
    global client
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
    
    return {"status": "success", "has_api_key": client is not None}

def attempt_auto_save(image_bytes: bytes, prefix: str, ext: str = "png"):
    auto_save_dir = os.environ.get("AUTO_SAVE_DIR", "").strip()
    if not auto_save_dir:
        return
        
    # Expand ~ to user home directory if needed
    save_dir = os.path.expanduser(auto_save_dir)
    
    if os.path.isdir(save_dir):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.{ext}"
        filepath = os.path.join(save_dir, filename)
        try:
            with open(filepath, "wb") as f:
                f.write(image_bytes)
            print(f"Auto-saved: {filepath}")
        except Exception as e:
            print(f"Warning: Failed to auto-save to {filepath}. Error: {e}")
    else:
        print(f"Warning: Auto-save directory does not exist: {save_dir}")

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
    if client is None:
        raise HTTPException(status_code=500, detail="Gemini Client is not configured. Missing GEMINI_API_KEY.")
    
    try:
        # Load the base image if provided
        base_image = None
        if file:
            contents = await file.read()
            base_image = Image.open(io.BytesIO(contents))
        
        # Configure Gemini parameters
        config_kwargs = {
            "number_of_images": 1,
            "aspect_ratio": aspect_ratio,
            "output_mime_type": "image/png"
        }
        
        # Only add output_resolution if explicitly provided, as "1K" or "2K"
        if output_resolution in ["1K", "2K"]:
            config_kwargs["output_resolution"] = output_resolution
            
        config = types.GenerateImagesConfig(**config_kwargs)
        
        # Wait for our turn in the rate-limit queue
        try:
            delay_seconds = float(os.environ.get("RATE_LIMIT_DELAY", 4.0))
        except (ValueError, TypeError):
            delay_seconds = 4.0
        await wait_for_rate_limit(min_delay_seconds=delay_seconds)

        # If there's a base image (image-to-image), we pass it as a list with the prompt
        if base_image:
            # Note: For image-to-image, Gemini expects the Image object directly
            inputs = [prompt, base_image]
            # Offload synchronous SDK call to a thread so the async queue continues processing
            result = await asyncio.to_thread(
                client.models.generate_images,
                model=model,
                prompt=inputs,
                config=config
            )
        else:
            # Standard Text-to-Image
            result = await asyncio.to_thread(
                client.models.generate_images,
                model=model,
                prompt=prompt,
                config=config
            )
        
        # Generated image bytes
        if not result.generated_images or len(result.generated_images) == 0:
            raise HTTPException(status_code=500, detail="No images generated.")
            
        generated_image = result.generated_images[0]
        image_bytes = generated_image.image.image_bytes
        
        # We always get PNG from Gemini as per config.
        # Check if we need to process image (crop or convert format).
        needs_processing = bool((target_width and target_height) or output_format.lower() == "webp")
        
        if needs_processing:
            try:
                img = Image.open(io.BytesIO(image_bytes))
                
                # Apply exact dimensions if requested using center-crop (cover)
                if target_width and target_height:
                    # Calculate Target vs Current ratios
                    target_ratio = target_width / target_height
                    current_ratio = img.width / img.height
                    
                    # Scale down so the smallest edge perfectly matches
                    if target_ratio > current_ratio:
                        # Target is wider than current. Match width first.
                        new_width = target_width
                        new_height = int(target_width / current_ratio)
                    else:
                        # Target is taller than current. Match height first.
                        new_height = target_height
                        new_width = int(target_height * current_ratio)

                    # Resize image precisely
                    # Image.Resampling.LANCZOS guarantees high-quality downsampling
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    # Perform the center crop
                    left = (img.width - target_width) / 2
                    top = (img.height - target_height) / 2
                    right = (img.width + target_width) / 2
                    bottom = (img.height + target_height) / 2
                    
                    img = img.crop((left, top, right, bottom))
                
                # Re-encode to bytes in the requested format
                img_byte_arr = io.BytesIO()
                save_format = 'WEBP' if output_format.lower() == 'webp' else 'PNG'
                img.save(img_byte_arr, format=save_format)
                image_bytes = img_byte_arr.getvalue()
                
            except Exception as e:
                print(f"Warning: Failed to process image (crop or convert). Returning raw origin image. Error: {e}")
                
        ext = output_format.lower() if output_format.lower() in ["png", "webp"] else "png"
        attempt_auto_save(image_bytes, "gen", ext)
        
        media_type = f"image/{ext}"
        # Return as raw image data for immediate display/download
        return Response(content=image_bytes, media_type=media_type)

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
        # Read the file
        contents = await file.read()
        
        # 1. Run local background removal
        no_bg_bytes = remove(contents)
        
        # 2. Trim to only the visible pixels
        no_bg_image = Image.open(io.BytesIO(no_bg_bytes)).convert("RGBA")
        bbox = no_bg_image.getbbox()
        
        if bbox:
            trimmed_image = no_bg_image.crop(bbox)
        else:
            trimmed_image = no_bg_image # Fallback if empty image
            
        # Convert back to bytes for response
        img_byte_arr = io.BytesIO()
        ext = output_format.lower() if output_format.lower() in ["png", "webp"] else "png"
        save_format = 'WEBP' if ext == 'webp' else 'PNG'
        trimmed_image.save(img_byte_arr, format=save_format)
        final_bytes = img_byte_arr.getvalue()
        
        attempt_auto_save(final_bytes, "proc", ext)
        
        media_type = f"image/{ext}"
        return Response(content=final_bytes, media_type=media_type)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=43211, reload=True)

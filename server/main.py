import os
import io
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
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
    allow_origins=["*"], # In production, restrict to actual frontend origin
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

class GenerateRequest(BaseModel):
    prompt: str
    model: str = "imagen-4.0-generate-001" # Or imagen-4.0-fast-generate-001
    aspect_ratio: str = "1:1"

class ConfigRequest(BaseModel):
    api_key: str

@app.get("/api/v1/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/v1/config")
def get_config():
    api_key = os.environ.get("GEMINI_API_KEY", "")
    has_key = bool(api_key and api_key != "your_api_key_here" and api_key.strip() != "")
    return {"has_api_key": has_key}

@app.post("/api/v1/config")
def set_config(request: ConfigRequest):
    global client
    # Save to .env file
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    
    # Simple write, overwriting the file with just the key (sufficient for this project)
    with open(env_path, 'w') as f:
        f.write(f'GEMINI_API_KEY="{request.api_key}"\n')
        
    # Update current process environment
    os.environ["GEMINI_API_KEY"] = request.api_key
    
    # Reinitialize client
    init_gemini_client()
    
    return {"status": "success", "has_api_key": client is not None}

@app.post("/api/v1/generate")
def generate_image(request: GenerateRequest):
    if client is None:
        raise HTTPException(status_code=500, detail="Gemini Client is not configured. Missing GEMINI_API_KEY.")
    
    try:
        # We need to map the prompt to Gemini generate parameters.
        result = client.models.generate_images(
            model=request.model,
            prompt=request.prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=request.aspect_ratio,
                output_mime_type="image/png"
            )
        )
        
        # Generated image bytes
        if len(result.generated_images) == 0:
            raise HTTPException(status_code=500, detail="No images generated.")
            
        generated_image = result.generated_images[0]
        # Return as raw image data for immediate display/download
        return Response(content=generated_image.image.image_bytes, media_type="image/png")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/process")
async def process_image(file: UploadFile = File(...)):
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
        trimmed_image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        return Response(content=img_byte_arr, media_type="image/png")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=43211, reload=True)

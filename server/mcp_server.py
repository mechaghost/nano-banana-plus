from fastmcp import FastMCP
from typing import Optional
from core import init_gemini_client, core_generate_image, core_process_image
import os
import base64

# Create an MCP server
mcp = FastMCP("Nano-Banana-Plus API")

# Initialize Gemini Client lazily or from env.
init_gemini_client()


@mcp.tool()
async def generate_image(
    prompt: str,
    model: str = "imagen-4.0-fast-generate-001",
    aspect_ratio: str = "1:1",
    output_resolution: str = "",
    output_format: str = "png",
    target_width: Optional[int] = None,
    target_height: Optional[int] = None,
) -> str:
    """
    Generates an image via the local Gemini integration and saves it to the output directory 
    or returns as base64 string if requested.

    Args:
        prompt: Detailed description of the image to generate.
        model: 'imagen-4.0-fast-generate-001' (Standard), 'imagen-4.0-fast-generate-001' (Drafts), 'imagen-4.0-ultra-generate-001' (High Quality).
        aspect_ratio: Defaults to 1:1. Valid options include 1:1, 3:4, 4:3, 9:16, 16:9.
        output_resolution: Defaults to "" (1K). Can be "2K" if the Ultra model is used.
        output_format: "png" (default) or "webp".
        target_width: Exact pixel target width to crop the image to perfectly match aspect ratio.
        target_height: Exact pixel target height to crop the image to perfectly match aspect ratio.

    Returns:
        Base64-encoded string representing the image bytes perfectly sized.
    """
    try:
        image_bytes, media_type = await core_generate_image(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            output_resolution=output_resolution,
            output_format=output_format,
            target_width=target_width,
            target_height=target_height,
            base_image_bytes=None # Image-to-image usually omitted unless requested. Could add a base64 field if needed.
        )
        # Convert to Base64 to return cleanly over MCP protocol
        b64_img = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:{media_type};base64,{b64_img}"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def remove_background_and_crop(
    image_base64: str,
    output_format: str = "png"
) -> str:
    """
    Removes the background from the provided image and tightly bounds the subject.

    Args:
        image_base64: Raw base64 string of the image (e.g. "iVBORw0KGgoAAAANSUhEUgAA...") do not include the data URL header.
        output_format: "png" (default) or "webp".

    Returns:
        Base64-encoded string representing the newly processed image.
    """
    try:
        # Check if the user accidentally passed a payload like "data:image/png;base64,xxxx"
        if image_base64.startswith("data:"):
            image_base64 = image_base64.split(",")[1]
            
        img_bytes = base64.b64decode(image_base64)
        final_bytes, media_type = await core_process_image(img_bytes, output_format)
        
        b64_img = base64.b64encode(final_bytes).decode('utf-8')
        return f"data:{media_type};base64,{b64_img}"
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    mcp.run()

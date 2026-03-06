import os
import uuid
import aiofiles
from fastapi import UploadFile, HTTPException
from PIL import Image
import io
from app.core.config import settings

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024  # bytes


async def save_upload_file(file: UploadFile, subfolder: str = "photos") -> str:
    """Save uploaded file, validate, resize if needed. Returns relative path."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{file.content_type}' not allowed. Use JPEG, PNG, WEBP or GIF."
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds {settings.MAX_FILE_SIZE_MB}MB limit."
        )

    # Process image with Pillow
    try:
        img = Image.open(io.BytesIO(contents))
        img = img.convert("RGB")
        # Resize if too large
        max_dim = 1920
        if img.width > max_dim or img.height > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)
        # Re-encode to JPEG
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=85, optimize=True)
        contents = output.getvalue()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file.")

    # Save to disk
    filename = f"{uuid.uuid4().hex}.jpg"
    dir_path = os.path.join(settings.UPLOAD_DIR, subfolder)
    os.makedirs(dir_path, exist_ok=True)
    filepath = os.path.join(dir_path, filename)

    async with aiofiles.open(filepath, "wb") as f:
        await f.write(contents)

    return f"{subfolder}/{filename}"


async def delete_file(relative_path: str):
    """Delete a file from uploads."""
    if not relative_path:
        return
    full_path = os.path.join(settings.UPLOAD_DIR, relative_path)
    if os.path.exists(full_path):
        os.remove(full_path)

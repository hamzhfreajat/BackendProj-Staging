import os
import io
import logging
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Request
from typing import List
import uuid

import boto3
from botocore.client import Config

from auth import get_real_ip
from security_events import log_file_upload_blocked

import auth
import models

logger = logging.getLogger(__name__)

# Define a simple media router
router = APIRouter(prefix="/api/media", tags=["media"])

def get_r2_client():
    from dotenv import load_dotenv
    load_dotenv('.env') # Force reload in case
    
    ak = os.getenv("R2_ACCESS_KEY_ID")
    sk = os.getenv("R2_SECRET_ACCESS_KEY")
    eu = os.getenv("R2_ENDPOINT_URL")
    
    logger.debug(f"R2 Setup -> AK configured: {bool(ak)}, EU configured: {bool(eu)}")
    
    if not ak or not eu:
        return None
    return boto3.client(
        's3',
        aws_access_key_id=ak,
        aws_secret_access_key=sk,
        endpoint_url=eu,
        region_name="auto",
        config=Config(signature_version='s3v4', connect_timeout=5, read_timeout=30, retries={'max_attempts': 1})
    )

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", dependencies=[Depends(auth.get_rate_limiter(10, 60))])
async def upload_media(
    request: Request,
    bypass_watermark: bool = False,
    files: List[UploadFile] = File(...), 
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Receives multiple files, saves them to Cloudflare R2 (or locally if missing config),
    and returns a list of URLs pointing to the saved files.
    """
    uploaded_urls = []
    
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="A maximum of 20 files is allowed per request.")
        
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.mp4', '.mov', '.pdf', '.m4a', '.mp3', '.aac', '.wav', '.ogg'}
    
    r2_client = get_r2_client()
    
    from fb_batch_router import check_image_bytes_for_watermark
    
    for file in files:
        file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
        
        # Security: Whitelist file extensions
        if file_ext not in ALLOWED_EXTENSIONS:
            log_file_upload_blocked(get_real_ip(request), request.url.path, f"Extension {file_ext} not allowed", str(current_user.id))
            raise HTTPException(status_code=400, detail=f"File extension {file_ext} is not allowed for security reasons.")
            
        # Security: Max File Size 50MB
        content = bytearray()
        while chunk := await file.read(1024 * 1024): # 1MB chunks
            content.extend(chunk)
            if len(content) > 50 * 1024 * 1024:
                log_file_upload_blocked(get_real_ip(request), request.url.path, f"File {file.filename} exceeds 50MB limit", str(current_user.id))
                raise HTTPException(status_code=413, detail="File too large. Maximum size is 50MB.")
        content = bytes(content)
        
        # Check for watermarks on image uploads
        is_image = file.content_type and file.content_type.startswith('image/')
        if not is_image and file_ext in ['.jpg', '.jpeg', '.png', '.webp', '.heic']:
            is_image = True
            
        if is_image:
            should_bypass_watermark = bypass_watermark or current_user.user_type == "admin"

            # Normal path: resize, compress and store the full and card sizes (see image_processing.py)
            try:
                from PIL import Image as PILImage
                from image_processing import store_image
                uploaded_urls.append(store_image(
                    content,
                    r2_client=r2_client,
                    watermark=not should_bypass_watermark,
                    upload_dir=UPLOAD_DIR,
                ))
                continue
            except PILImage.DecompressionBombError:
                log_file_upload_blocked(get_real_ip(request), request.url.path, "Decompression Bomb Detected", str(current_user.id))
                raise HTTPException(status_code=400, detail="Image pixel limit exceeded. File is too large.")
            except Exception as e:
                # e.g. HEIC without a decoder: store the original file as before
                logger.error(f"Image processing failed, storing original: {e}")
            # Watermark check bypassed for add ads per user request
            # if not should_bypass_watermark and check_image_bytes_for_watermark(content):
            #     raise HTTPException(status_code=400, detail="Watermark found")
            
            # --- APPLY WATERMARK ---
            if not should_bypass_watermark:
                try:
                    from PIL import Image
                    # Security: Enforce pixel limit to prevent Decompression Bombs (OOM DoS)
                    Image.MAX_IMAGE_PIXELS = 10_000_000
                    
                    uploaded_img = Image.open(io.BytesIO(content)).convert("RGBA")
                    watermark_path = "static/watermark.png"
                    if os.path.exists(watermark_path):
                        watermark = Image.open(watermark_path).convert("RGBA")
                        
                        target_width = int(uploaded_img.width * 0.25)
                        target_width = max(100, min(target_width, 800))
                        
                        aspect_ratio = watermark.width / watermark.height
                        target_height = int(target_width / aspect_ratio)
                        watermark = watermark.resize((target_width, target_height), Image.Resampling.LANCZOS)
                        
                        padding = int(uploaded_img.width * 0.03)
                        position = (padding, uploaded_img.height - watermark.height - padding)
                        
                        composite = Image.new("RGBA", uploaded_img.size)
                        composite.paste(uploaded_img, (0,0))
                        composite.paste(watermark, position, mask=watermark)
                        
                        if file_ext in ['.jpg', '.jpeg']:
                            final_img = composite.convert("RGB")
                            save_format = "JPEG"
                        else:
                            final_img = composite
                            save_format = "PNG"
                            
                        out_buffer = io.BytesIO()
                        final_img.save(out_buffer, format=save_format, quality=90)
                        content = out_buffer.getvalue()
                except Image.DecompressionBombError as e:
                    log_file_upload_blocked(get_real_ip(request), request.url.path, "Decompression Bomb Detected", str(current_user.id))
                    raise HTTPException(status_code=400, detail="Image pixel limit exceeded. File is too large.")
                except Exception as e:
                    logger.error(f"Failed to apply watermark: {e}")
            # -----------------------
            
            file_obj_to_upload = io.BytesIO(content)
        else:
            if file_ext == '.wav':
                try:
                    import wave
                    with wave.open(io.BytesIO(content), 'rb') as w:
                        frames = w.getnframes()
                        rate = w.getframerate()
                        duration = frames / float(rate)
                        if duration > 610:  # 10 minutes + 10s buffer
                            log_file_upload_blocked(get_real_ip(request), request.url.path, "Audio exceeds 10 minutes", str(current_user.id))
                            raise HTTPException(status_code=400, detail="Voice message exceeds the maximum allowed duration of 10 minutes.")
                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"Failed to check audio duration: {e}")
                    
            file_obj_to_upload = file.file
            file_obj_to_upload.seek(0)

        # Generate a unique filename to prevent collisions
        file_ext = os.path.splitext(file.filename)[1] if file.filename else ""
        unique_filename = f"{uuid.uuid4().hex}{file_ext}"
        
        r2_client = get_r2_client()
        bucket_name = os.getenv("R2_BUCKET_NAME", "joapp-ads")
        public_url = os.getenv("R2_PUBLIC_URL")
        if not public_url:
            logger.warning("R2_PUBLIC_URL not set. Using default fallback.")
            public_url = "https://pub-158212dafa5344d4bbf078a74da2305a.r2.dev"

        # Determine strict MIME type from extension
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.webp': 'image/webp',
            '.heic': 'image/heic',
            '.mp4': 'video/mp4',
            '.mov': 'video/quicktime',
            '.pdf': 'application/pdf',
            '.m4a': 'audio/mp4',
            '.mp3': 'audio/mpeg',
            '.aac': 'audio/aac',
            '.wav': 'audio/wav',
            '.ogg': 'audio/ogg'
        }
        strict_content_type = mime_types.get(file_ext.lower(), 'application/octet-stream')

        if r2_client:
            # Upload to Cloudflare R2
            try:
                logger.info(f"Uploading {unique_filename} to Cloudflare R2...")
                file_obj_to_upload.seek(0)
                r2_client.upload_fileobj(
                    file_obj_to_upload, 
                    bucket_name, 
                    unique_filename,
                    ExtraArgs={'ContentType': strict_content_type}
                )
                
                # Construct public URL
                public_url_base = public_url.rstrip('/')
                file_url = f"{public_url_base}/{unique_filename}"
                uploaded_urls.append(file_url)
                logger.info(f"R2 Upload successful: {file_url}")
                
            except Exception as e:
                logger.error(f"R2 Upload Exception: {e}")
                raise HTTPException(status_code=500, detail="Failed to upload image to Cloudflare R2")
        else:
            # Fallback to Local Upload
            file_path = os.path.join(UPLOAD_DIR, unique_filename)
            with open(file_path, "wb") as buffer:
                file_obj_to_upload.seek(0)
                buffer.write(file_obj_to_upload.read())
                
            file_url = f"/uploads/{unique_filename}"
            uploaded_urls.append(file_url)
        
    return {"urls": uploaded_urls}

@router.post("/check-watermarks")
async def check_watermarks(
    files: List[UploadFile] = File(...),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Receives multiple files and ONLY checks them for watermarks.
    Returns 200 OK if clean, 400 Bad Request if a watermark is found.
    (Watermark check disabled per user request)
    """
    return {"status": "clean"}

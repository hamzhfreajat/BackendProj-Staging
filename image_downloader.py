import os
import io
import uuid
import logging
import requests
from botocore.client import Config
import boto3

logger = logging.getLogger(__name__)

def get_r2_client():
    from dotenv import load_dotenv
    load_dotenv('.env')
    ak = os.getenv("R2_ACCESS_KEY_ID")
    sk = os.getenv("R2_SECRET_ACCESS_KEY")
    eu = os.getenv("R2_ENDPOINT_URL")
    if not ak or not eu: return None
    return boto3.client(
        's3', aws_access_key_id=ak, aws_secret_access_key=sk,
        endpoint_url=eu, region_name="auto",
        config=Config(signature_version='s3v4', connect_timeout=5, read_timeout=30)
    )

def download_and_upload_image(url: str) -> str:
    """Downloads an image from a URL and uploads it to Cloudflare R2. Returns the R2 URL or None if failed."""
    if not url or "fbcdn.net" not in url:
        return url # Return as is if not FB or invalid
        
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            logger.error(f"Failed to download image, status {resp.status_code}")
            return None
            
        content = resp.content
        if not content: return None
        
        # Simple R2 upload
        r2 = get_r2_client()
        if not r2: return url
        
        # Normal path: resize, compress and store the full and card sizes (see image_processing.py)
        try:
            from image_processing import store_image
            return store_image(content, r2_client=r2)
        except Exception as e:
            logger.error(f"Image processing failed, storing original: {e}")

        bucket_name = os.getenv("R2_BUCKET_NAME", "joapp-ads")
        public_url = os.getenv("R2_PUBLIC_URL", "https://pub-158212dafa5344d4bbf078a74da2305a.r2.dev").rstrip('/')
        
        file_ext = ".jpg"
        if "png" in resp.headers.get("Content-Type", "").lower(): file_ext = ".png"
        
        unique_filename = f"{uuid.uuid4().hex}{file_ext}"
        
        r2.upload_fileobj(
            io.BytesIO(content), 
            bucket_name, 
            unique_filename,
            ExtraArgs={'ContentType': resp.headers.get("Content-Type", "image/jpeg")}
        )
        return f"{public_url}/{unique_filename}"
        
    except Exception as e:
        logger.error(f"Error downloading/uploading image: {e}")
        return None

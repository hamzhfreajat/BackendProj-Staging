"""
Single place where ad images are prepared for serving.

Every image (uploaded by a user or pulled in by the scraper) is stored twice:

    img/<id>.jpg     full size, long edge <= 1600px  -> ad details / gallery
    img/<id>_m.jpg   card size, <= 900px wide        -> listing cards

Both are progressive JPEGs with a one-year immutable cache header, so the CDN
and the app can cache them forever (the name changes whenever the image does).

The app derives the card URL from the full URL (".jpg" -> "_m.jpg") for any
URL under "img/", see ApiService.cardImageUrl in the Flutter app. Keep the two
in sync if the naming ever changes.
"""
import io
import os
import uuid
import logging

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# Above 2x this Pillow raises DecompressionBombError (50MP: covers current phone cameras)
Image.MAX_IMAGE_PIXELS = 25_000_000

IMAGE_PREFIX = "img/"
CARD_SUFFIX = "_m"
FULL_MAX_EDGE = 1600
CARD_MAX_SIZE = (900, 1200)
FULL_QUALITY = 82
CARD_QUALITY = 76
CACHE_CONTROL = "public, max-age=31536000, immutable"
WATERMARK_PATH = "static/watermark.png"
DEFAULT_PUBLIC_URL = "https://pub-158212dafa5344d4bbf078a74da2305a.r2.dev"


def _encode(img: Image.Image, quality: int) -> bytes:
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality, optimize=True, progressive=True)
    return out.getvalue()


def _apply_watermark(img: Image.Image) -> Image.Image:
    if not os.path.exists(WATERMARK_PATH):
        return img
    watermark = Image.open(WATERMARK_PATH).convert("RGBA")
    target_width = max(100, min(int(img.width * 0.25), 800))
    target_height = int(target_width / (watermark.width / watermark.height))
    watermark = watermark.resize((target_width, target_height), Image.Resampling.LANCZOS)

    padding = int(img.width * 0.03)
    position = (padding, img.height - watermark.height - padding)
    composite = img.convert("RGBA")
    composite.paste(watermark, position, mask=watermark)
    return composite.convert("RGB")


def process_image(content: bytes, watermark: bool = False):
    """
    Returns (full_bytes, card_bytes) as JPEG.
    Raises Image.DecompressionBombError for absurdly large images and any other
    PIL error for content it can't read (e.g. HEIC without a decoder).
    """
    img = Image.open(io.BytesIO(content))
    # Phone photos are stored sideways with an EXIF flag; bake the rotation in
    img = ImageOps.exif_transpose(img)

    if img.mode in ("RGBA", "LA", "P"):
        # Flatten transparency onto white (JPEG has no alpha channel)
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    img.thumbnail((FULL_MAX_EDGE, FULL_MAX_EDGE), Image.Resampling.LANCZOS)
    if watermark:
        img = _apply_watermark(img)

    card = img.copy()
    card.thumbnail(CARD_MAX_SIZE, Image.Resampling.LANCZOS)

    return _encode(img, FULL_QUALITY), _encode(card, CARD_QUALITY)


def card_url(url: str) -> str:
    """Card-size URL for an image stored by store_image; other URLs are returned unchanged."""
    if url and f"/{IMAGE_PREFIX}" in url and url.endswith(".jpg") and not url.endswith(f"{CARD_SUFFIX}.jpg"):
        return url[: -len(".jpg")] + f"{CARD_SUFFIX}.jpg"
    return url


def store_image(content: bytes, r2_client=None, watermark: bool = False, upload_dir: str = "uploads") -> str:
    """
    Processes an image and stores both sizes. Returns the URL of the full-size image.
    Uses Cloudflare R2 when a client is given, otherwise the local uploads folder.
    Raises on images that can't be processed, so callers can decide how to fall back.
    """
    full_bytes, card_bytes = process_image(content, watermark=watermark)
    image_id = uuid.uuid4().hex
    full_key = f"{IMAGE_PREFIX}{image_id}.jpg"
    card_key = f"{IMAGE_PREFIX}{image_id}{CARD_SUFFIX}.jpg"

    if r2_client:
        bucket_name = os.getenv("R2_BUCKET_NAME", "joapp-ads")
        public_url = (os.getenv("R2_PUBLIC_URL") or DEFAULT_PUBLIC_URL).rstrip("/")
        extra_args = {"ContentType": "image/jpeg", "CacheControl": CACHE_CONTROL}
        # Card first: the full URL is only handed out once both sizes exist
        r2_client.upload_fileobj(io.BytesIO(card_bytes), bucket_name, card_key, ExtraArgs=extra_args)
        r2_client.upload_fileobj(io.BytesIO(full_bytes), bucket_name, full_key, ExtraArgs=extra_args)
        return f"{public_url}/{full_key}"

    os.makedirs(os.path.join(upload_dir, IMAGE_PREFIX), exist_ok=True)
    for key, data in ((card_key, card_bytes), (full_key, full_bytes)):
        with open(os.path.join(upload_dir, key), "wb") as f:
            f.write(data)
    return f"/{upload_dir}/{full_key}"

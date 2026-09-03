import os
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

# Track if Cloudinary is configured
_cloudinary_ready = False
try:
    if settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET:
        import cloudinary
        import cloudinary.uploader
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True
        )
        _cloudinary_ready = True
        logger.info("Cloudinary storage successfully configured.")
except Exception as e:
    logger.warning("Cloudinary initialization failed: %s. Using local disk fallback.", e)


def upload_file_bytes(
    file_bytes: bytes,
    filename: str,
    folder: str = "academiq",
    resource_type: str = "auto"
) -> dict:
    """
    Uploads raw file bytes to Cloudinary or falls back to local uploads/ directory.
    Returns: { url, public_id, size, filename }
    """
    if _cloudinary_ready:
        try:
            import cloudinary.uploader
            res = cloudinary.uploader.upload(
                file_bytes,
                folder=folder,
                resource_type=resource_type,
                filename_override=filename
            )
            return {
                "url": res.get("secure_url", res.get("url")),
                "public_id": res.get("public_id"),
                "size": res.get("bytes", len(file_bytes)),
                "filename": filename
            }
        except Exception as e:
            logger.error("Cloudinary upload failed: %s. Falling back to local storage.", e)

    # Local Disk Fallback
    local_dir = os.path.join(os.getcwd(), "uploads", folder)
    os.makedirs(local_dir, exist_ok=True)
    local_path = os.path.join(local_dir, filename)

    with open(local_path, "wb") as f:
        f.write(file_bytes)

    relative_url = f"/uploads/{folder}/{filename}"
    return {
        "url": relative_url,
        "public_id": f"{folder}/{filename}",
        "size": len(file_bytes),
        "filename": filename
    }


def delete_file(public_id: str, resource_type: str = "image") -> bool:
    """Deletes asset from Cloudinary or removes from local storage fallback."""
    if _cloudinary_ready:
        try:
            import cloudinary.uploader
            res = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
            return res.get("result") in ["ok", "not found"]
        except Exception as e:
            logger.error("Cloudinary destroy failed: %s", e)

    # Local Disk Fallback
    local_path = os.path.join(os.getcwd(), "uploads", public_id)
    if os.path.exists(local_path):
        try:
            os.remove(local_path)
            return True
        except Exception as e:
            logger.error("Local file removal failed: %s", e)
            return False
    return True

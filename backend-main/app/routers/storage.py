import uuid
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from app.dependencies import get_current_user
from app.models.user import User
from app.services.storage_service import upload_file_bytes

router = APIRouter()

class UploadResponse(BaseModel):
    url: str
    public_id: str
    filename: str
    size: int
    message: str

@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_asset(
    file: UploadFile = File(...),
    folder: Optional[str] = Form("general"),
    current_user: User = Depends(get_current_user)
):
    """
    Uploads a file (image, PDF document, video) to Cloudinary or local storage fallback.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename missing in upload payload")

    # Generate safe unique filename
    ext = file.filename.split(".")[-1] if "." in file.filename else ""
    safe_name = f"{uuid.uuid4()}.{ext}" if ext else str(uuid.uuid4())

    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    result = upload_file_bytes(
        file_bytes=contents,
        filename=safe_name,
        folder=folder or "general"
    )

    return UploadResponse(
        url=result["url"],
        public_id=result["public_id"],
        filename=result["filename"],
        size=result["size"],
        message="Asset uploaded successfully"
    )

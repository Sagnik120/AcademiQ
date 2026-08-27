from fastapi import APIRouter, HTTPException
from app.schemas import ExtractPDFRequest, ExtractPDFResponse
from app.services.pdf_parser import extract_pdf
import logging

router = APIRouter(tags=["pdf"])
logger = logging.getLogger(__name__)


@router.post("/extract-pdf", response_model=ExtractPDFResponse)
async def extract(request: ExtractPDFRequest):
    try:
        result = extract_pdf(request.file_bytes)
        return ExtractPDFResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("PDF extraction failed: %s", e)
        raise HTTPException(status_code=500, detail="PDF extraction failed.")

import base64
import io
import re
import logging

logger = logging.getLogger(__name__)


def _clean_text(text: str) -> str:
    """Strip excess whitespace and common PDF artefacts."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)  # lone page numbers
    return text.strip()


def _is_garbled(text: str) -> bool:
    """Heuristic: if more than 20% of chars are non-ASCII, likely garbled."""
    if not text:
        return True
    non_ascii = sum(1 for c in text if ord(c) > 127)
    return (non_ascii / len(text)) > 0.2


def _try_pypdf2(file_bytes: bytes) -> tuple[str, int]:
    import PyPDF2
    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
    return "\n".join(pages), len(reader.pages)


def _try_pdfplumber(file_bytes: bytes) -> tuple[str, int]:
    import pdfplumber
    pages = []
    page_count = 0
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text)
    return "\n".join(pages), page_count


def extract_pdf(file_b64: str) -> dict:
    """
    Try PyPDF2, fall back to pdfplumber if empty/garbled.
    Returns dict with text, page_count, extraction_method, char_count.
    Raises ValueError for scanned (image-only) PDFs.
    """
    file_bytes = base64.b64decode(file_b64)
    method = "pypdf2"
    text = ""
    page_count = 0

    try:
        text, page_count = _try_pypdf2(file_bytes)
        if _is_garbled(text) or not text.strip():
            logger.info("PyPDF2 returned empty/garbled text — trying pdfplumber")
            text, page_count = _try_pdfplumber(file_bytes)
            method = "pdfplumber"
    except Exception as e:
        logger.warning("PyPDF2 failed (%s), trying pdfplumber", e)
        try:
            text, page_count = _try_pdfplumber(file_bytes)
            method = "pdfplumber"
        except Exception as e2:
            raise ValueError(f"Both extractors failed: {e2}") from e2

    text = _clean_text(text)

    if not text.strip():
        raise ValueError(
            "No text could be extracted. This appears to be a scanned (image-based) PDF. "
            "Please upload a text-based PDF."
        )

    return {
        "text": text,
        "page_count": page_count,
        "extraction_method": method,
        "char_count": len(text),
    }

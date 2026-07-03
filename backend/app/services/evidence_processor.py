import hashlib
import mimetypes
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.models import Evidence, EvidenceStatus

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}
PDF_EXTENSIONS = {".pdf"}
PLAIN_TEXT_EXTENSIONS = {".txt", ".csv", ".log"}

CHUNK_SIZE = 1024 * 1024  # 1MB


def compute_hashes(file_path: Path) -> tuple[str, str]:
    """Real SHA256 and MD5 computation, streamed so large files don't blow memory."""
    sha256 = hashlib.sha256()
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            sha256.update(chunk)
            md5.update(chunk)
    return sha256.hexdigest(), md5.hexdigest()


def extract_text_from_image(file_path: Path) -> tuple[str | None, int | None]:
    """Real OCR using Tesseract via pytesseract. Returns (text, mean_confidence)."""
    import pytesseract
    from PIL import Image

    image = Image.open(file_path)
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    words = [w for w in data["text"] if w.strip()]
    confidences = [int(c) for c, w in zip(data["conf"], data["text"]) if w.strip() and int(c) >= 0]
    text = " ".join(words)
    mean_conf = round(sum(confidences) / len(confidences)) if confidences else None
    return (text or None), mean_conf


def extract_text_from_pdf(file_path: Path) -> tuple[str | None, str]:
    """Real PDF text-layer extraction using pypdf. Falls back to noting scanned PDFs."""
    from pypdf import PdfReader

    reader = PdfReader(str(file_path))
    pages_text = []
    for page in reader.pages:
        t = page.extract_text() or ""
        pages_text.append(t)
    full_text = "\n".join(pages_text).strip()
    if full_text:
        return full_text, "pdf_text_layer"
    return None, "pdf_text_layer_empty_likely_scanned"


def extract_text_from_plain(file_path: Path) -> str | None:
    try:
        return file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def find_duplicate(db: Session, case_id: str, sha256_hash: str, exclude_id: str) -> str | None:
    existing = (
        db.query(Evidence)
        .filter(Evidence.case_id == case_id, Evidence.sha256_hash == sha256_hash, Evidence.id != exclude_id)
        .first()
    )
    return existing.id if existing else None


def process_evidence(db: Session, evidence_id: str) -> Evidence:
    """
    Real end-to-end processing pipeline for one evidence file:
    hash -> metadata -> duplicate check -> text extraction (OCR / PDF / plain) -> persist.
    Runs synchronously (in-request) for Phase 1; swap for a Celery task in Phase 2+
    without changing this function's logic.
    """
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise ValueError(f"Evidence {evidence_id} not found")

    file_path = Path(evidence.stored_path)
    evidence.status = EvidenceStatus.processing
    db.commit()

    try:
        sha256_hash, md5_hash = compute_hashes(file_path)
        evidence.sha256_hash = sha256_hash
        evidence.md5_hash = md5_hash
        evidence.file_size_bytes = file_path.stat().st_size

        mime_type, _ = mimetypes.guess_type(str(file_path))
        evidence.mime_type = mime_type
        evidence.file_extension = file_path.suffix.lower()

        dup_id = find_duplicate(db, evidence.case_id, sha256_hash, evidence.id)
        evidence.is_duplicate_of = dup_id

        ext = file_path.suffix.lower()
        text, method, confidence = None, None, None

        if ext in IMAGE_EXTENSIONS:
            text, confidence = extract_text_from_image(file_path)
            method = "ocr_tesseract"
        elif ext in PDF_EXTENSIONS:
            text, method = extract_text_from_pdf(file_path)
        elif ext in PLAIN_TEXT_EXTENSIONS:
            text = extract_text_from_plain(file_path)
            method = "plain_text_read"
        else:
            method = "unsupported_for_text_extraction_in_phase1"

        evidence.extracted_text = text
        evidence.extraction_method = method
        evidence.extraction_confidence = confidence
        evidence.status = EvidenceStatus.processed
        evidence.processed_at = datetime.now(timezone.utc)
        evidence.processing_error = None

    except Exception as e:
        evidence.status = EvidenceStatus.failed
        evidence.processing_error = str(e)

    db.commit()
    db.refresh(evidence)
    return evidence

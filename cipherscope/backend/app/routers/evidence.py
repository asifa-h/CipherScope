import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.models import Case, Evidence, User, AuditLog, EvidenceStatus
from app.schemas.schemas import EvidenceOut
from app.services.object_storage import evidence_object_key, object_storage
from app.tasks.evidence import enqueue_evidence_processing

router = APIRouter(prefix="/cases/{case_id}/evidence", tags=["evidence"])


def _get_owned_case(db: Session, case_id: str, user: User) -> Case:
    case = db.query(Case).filter(Case.id == case_id, Case.organization_id == user.organization_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post("", response_model=EvidenceOut, status_code=201)
async def upload_evidence(
    case_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = _get_owned_case(db, case_id, user)

    original_filename = file.filename or "evidence"
    object_key = evidence_object_key(case.id, original_filename)
    size = 0
    file_descriptor, temporary_name = tempfile.mkstemp(suffix=Path(original_filename).suffix)
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    try:
        with temporary_path.open("wb") as temporary_file:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="File exceeds max upload size")
                temporary_file.write(chunk)

            if size == 0:
                raise HTTPException(status_code=400, detail="Uploaded file is empty")

            temporary_file.flush()
        object_storage.upload_path(temporary_path, object_key, file.content_type)
    finally:
        temporary_path.unlink(missing_ok=True)

    evidence = Evidence(
        case_id=case.id,
        uploaded_by_id=user.id,
        original_filename=original_filename,
        stored_path=object_key,
        file_size_bytes=size,
        sha256_hash="pending",
        md5_hash="pending",
        status=EvidenceStatus.uploaded,
    )
    db.add(evidence)
    db.flush()
    db.add(AuditLog(case_id=case.id, user_id=user.id, action="evidence_uploaded", detail=original_filename))
    db.commit()
    db.refresh(evidence)

    try:
        enqueue_evidence_processing(evidence.id)
    except Exception as exc:
        # The upload is durable in MinIO, so callers can retry via the existing
        # reprocess endpoint if Redis is temporarily unavailable.
        evidence.status = EvidenceStatus.failed
        evidence.processing_error = f"Unable to queue evidence processing: {exc}"
        db.commit()

    db.refresh(evidence)
    return evidence


@router.get("", response_model=list[EvidenceOut])
def list_evidence(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = _get_owned_case(db, case_id, user)
    return db.query(Evidence).filter(Evidence.case_id == case.id).order_by(Evidence.uploaded_at.desc()).all()


@router.get("/{evidence_id}", response_model=EvidenceOut)
def get_evidence(case_id: str, evidence_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = _get_owned_case(db, case_id, user)
    ev = db.query(Evidence).filter(Evidence.id == evidence_id, Evidence.case_id == case.id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return ev


@router.post("/{evidence_id}/reprocess", response_model=EvidenceOut)
def reprocess_evidence(case_id: str, evidence_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = _get_owned_case(db, case_id, user)
    ev = db.query(Evidence).filter(Evidence.id == evidence_id, Evidence.case_id == case.id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evidence not found")

    ev.status = EvidenceStatus.uploaded
    ev.processing_error = None
    ev.processed_at = None
    ev.sha256_hash = "pending"
    ev.md5_hash = "pending"
    ev.extracted_text = None
    ev.extraction_method = None
    ev.extraction_confidence = None
    ev.is_duplicate_of = None
    db.commit()

    try:
        enqueue_evidence_processing(ev.id)
    except Exception as exc:
        ev.status = EvidenceStatus.failed
        ev.processing_error = f"Unable to queue evidence processing: {exc}"
        db.commit()

    db.refresh(ev)
    return ev

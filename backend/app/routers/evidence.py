import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.models import Case, Evidence, User, AuditLog, EvidenceStatus
from app.schemas.schemas import EvidenceOut
from app.services.evidence_processor import process_evidence

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

    # Stream to disk with a size cap, real bytes on real filesystem.
    case_dir = settings.STORAGE_DIR / case.id
    case_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4()}_{Path(file.filename).name}"
    dest_path = case_dir / safe_name

    size = 0
    with open(dest_path, "wb") as out_f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > settings.MAX_UPLOAD_BYTES:
                out_f.close()
                dest_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="File exceeds max upload size")
            out_f.write(chunk)

    if size == 0:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    evidence = Evidence(
        case_id=case.id,
        uploaded_by_id=user.id,
        original_filename=file.filename,
        stored_path=str(dest_path),
        file_size_bytes=size,
        sha256_hash="pending",
        md5_hash="pending",
        status=EvidenceStatus.uploaded,
    )
    db.add(evidence)
    db.flush()
    db.add(AuditLog(case_id=case.id, user_id=user.id, action="evidence_uploaded", detail=file.filename))
    db.commit()
    db.refresh(evidence)

    # Real synchronous processing (Phase 1). Phase 2+: dispatch to a Celery worker instead.
    evidence = process_evidence(db, evidence.id)
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
    return process_evidence(db, ev.id)

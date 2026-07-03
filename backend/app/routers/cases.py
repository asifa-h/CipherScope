import random
import string
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.models import Case, User, Evidence, AuditLog
from app.schemas.schemas import CaseCreate, CaseOut

router = APIRouter(prefix="/cases", tags=["cases"])


def generate_case_number() -> str:
    year = datetime.now(timezone.utc).strftime("%Y")
    suffix = "".join(random.choices(string.digits, k=6))
    return f"CS-{year}-{suffix}"


@router.post("", response_model=CaseOut, status_code=201)
def create_case(payload: CaseCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case_number = generate_case_number()
    while db.query(Case).filter(Case.case_number == case_number).first():
        case_number = generate_case_number()

    case = Case(
        organization_id=user.organization_id,
        created_by_id=user.id,
        case_number=case_number,
        title=payload.title,
        description=payload.description,
    )
    db.add(case)
    db.flush()
    db.add(AuditLog(case_id=case.id, user_id=user.id, action="case_created", detail=payload.title))
    db.commit()
    db.refresh(case)

    out = CaseOut.model_validate(case)
    out.evidence_count = 0
    return out


@router.get("", response_model=list[CaseOut])
def list_cases(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cases = db.query(Case).filter(Case.organization_id == user.organization_id).order_by(Case.created_at.desc()).all()
    results = []
    for c in cases:
        out = CaseOut.model_validate(c)
        out.evidence_count = db.query(Evidence).filter(Evidence.case_id == c.id).count()
        results.append(out)
    return results


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = db.query(Case).filter(Case.id == case_id, Case.organization_id == user.organization_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    out = CaseOut.model_validate(case)
    out.evidence_count = db.query(Evidence).filter(Evidence.case_id == case.id).count()
    return out

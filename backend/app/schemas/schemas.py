from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ---------- Auth ----------
class OrgRegister(BaseModel):
    organization_name: str = Field(..., min_length=2, max_length=200)
    full_name: str = Field(..., min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(..., min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    organization_id: str

    class Config:
        from_attributes = True


# ---------- Case ----------
class CaseCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=300)
    description: Optional[str] = None


class CaseOut(BaseModel):
    id: str
    case_number: str
    title: str
    description: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    evidence_count: int = 0

    class Config:
        from_attributes = True


# ---------- Evidence ----------
class EvidenceOut(BaseModel):
    id: str
    case_id: str
    original_filename: str
    mime_type: Optional[str]
    file_extension: Optional[str]
    file_size_bytes: int
    sha256_hash: str
    md5_hash: str
    status: str
    processing_error: Optional[str]
    extracted_text: Optional[str]
    extraction_method: Optional[str]
    extraction_confidence: Optional[int]
    is_duplicate_of: Optional[str]
    uploaded_at: datetime
    processed_at: Optional[datetime]

    class Config:
        from_attributes = True


class EvidenceSummary(BaseModel):
    id: str
    original_filename: str
    status: str
    file_size_bytes: int
    sha256_hash: str
    is_duplicate_of: Optional[str]
    uploaded_at: datetime

    class Config:
        from_attributes = True

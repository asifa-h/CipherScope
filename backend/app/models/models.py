import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (Column, String, DateTime, ForeignKey, Text, Enum,
                         Integer, BigInteger, Boolean)
from sqlalchemy.orm import relationship

from app.core.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    admin = "admin"
    investigator = "investigator"
    viewer = "viewer"


class EvidenceStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    processed = "processed"
    failed = "failed"


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=utcnow)

    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    cases = relationship("Case", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.investigator, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    organization = relationship("Organization", back_populates="users")
    cases_created = relationship("Case", back_populates="created_by")


class Case(Base):
    """An investigation."""
    __tablename__ = "cases"

    id = Column(String, primary_key=True, default=gen_uuid)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    created_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    case_number = Column(String, nullable=False, unique=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="open")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    organization = relationship("Organization", back_populates="cases")
    created_by = relationship("User", back_populates="cases_created")
    evidence_items = relationship("Evidence", back_populates="case", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="case", cascade="all, delete-orphan")


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(String, primary_key=True, default=gen_uuid)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    uploaded_by_id = Column(String, ForeignKey("users.id"), nullable=False)

    original_filename = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    mime_type = Column(String, nullable=True)
    file_extension = Column(String, nullable=True)
    file_size_bytes = Column(BigInteger, nullable=False)

    sha256_hash = Column(String, nullable=False, index=True)
    md5_hash = Column(String, nullable=False, index=True)

    status = Column(Enum(EvidenceStatus), default=EvidenceStatus.uploaded, nullable=False)
    processing_error = Column(Text, nullable=True)

    extracted_text = Column(Text, nullable=True)
    extraction_method = Column(String, nullable=True)  # e.g. "ocr_tesseract", "pdf_text_layer"
    extraction_confidence = Column(Integer, nullable=True)  # 0-100, null if not applicable

    is_duplicate_of = Column(String, ForeignKey("evidence.id"), nullable=True)

    uploaded_at = Column(DateTime, default=utcnow)
    processed_at = Column(DateTime, nullable=True)

    case = relationship("Case", back_populates="evidence_items")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=gen_uuid)
    case_id = Column(String, ForeignKey("cases.id"), nullable=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    case = relationship("Case", back_populates="audit_logs")

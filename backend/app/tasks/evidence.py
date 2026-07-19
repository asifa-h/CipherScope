from app.core.database import SessionLocal
from app.services.evidence_processor import process_evidence
from app.worker import celery_app


@celery_app.task(name="cipherscope.process_evidence")
def process_evidence_task(evidence_id: str) -> dict[str, str]:
    """Process evidence in an independent database session owned by the worker."""
    db = SessionLocal()
    try:
        evidence = process_evidence(db, evidence_id)
        status = evidence.status.value if hasattr(evidence.status, "value") else str(evidence.status)
        return {"evidence_id": evidence.id, "status": status}
    finally:
        db.close()


def enqueue_evidence_processing(evidence_id: str) -> None:
    process_evidence_task.delay(evidence_id)

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    # SQLite remains supported only for isolated tests and one-off local tooling.
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://cipherscope:cipherscope@db:5432/cipherscope",
    )

    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

    MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", str(200 * 1024 * 1024)))  # 200MB

    # Production evidence storage.  `filesystem` is deliberately retained only
    # as a lightweight adapter for isolated automated tests.
    OBJECT_STORAGE_BACKEND: str = os.getenv("OBJECT_STORAGE_BACKEND", "s3").lower()
    STORAGE_DIR: Path = Path(os.getenv("LOCAL_STORAGE_DIR", str(BASE_DIR / "storage" / "evidence")))
    S3_ENDPOINT_URL: str | None = os.getenv("S3_ENDPOINT_URL", "http://minio:9000")
    S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY", "cipherscope-minio")
    S3_SECRET_KEY: str = os.getenv("S3_SECRET_KEY", "cipherscope-minio-change-me")
    S3_BUCKET: str = os.getenv("S3_BUCKET", "cipherscope-evidence")
    S3_REGION: str = os.getenv("S3_REGION", "us-east-1")

    # Redis is both the Celery broker and result backend.  Eager mode is used
    # only by the integration tests so their Phase 1 assertions stay unchanged.
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
    CELERY_TASK_ALWAYS_EAGER: bool = _as_bool(os.getenv("CELERY_TASK_ALWAYS_EAGER", "false"))

settings = Settings()
if settings.OBJECT_STORAGE_BACKEND == "filesystem":
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)

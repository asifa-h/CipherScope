import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings:
    # Swap DATABASE_URL to a Postgres DSN in production, e.g.:
    # postgresql+psycopg2://user:pass@host:5432/cipherscope
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/cipherscope.db")

    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

    STORAGE_DIR: Path = BASE_DIR / "storage" / "evidence"
    MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", str(200 * 1024 * 1024)))  # 200MB

settings = Settings()
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)

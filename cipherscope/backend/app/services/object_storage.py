"""S3-compatible evidence storage with a filesystem adapter for tests."""

from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile
from typing import Iterator

import boto3
from botocore.config import Config

from app.core.config import settings


class ObjectStorage:
    """Keeps evidence bytes out of the API and worker container filesystems."""

    def __init__(self) -> None:
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT_URL,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                region_name=settings.S3_REGION,
                config=Config(
                    s3={"addressing_style": "path"},
                    retries={"max_attempts": 3, "mode": "standard"},
                ),
            )
        return self._client

    def upload_path(self, source: Path, object_key: str, content_type: str | None = None) -> None:
        if settings.OBJECT_STORAGE_BACKEND == "filesystem":
            destination = settings.STORAGE_DIR / object_key
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            return

        extra_args = {"ContentType": content_type} if content_type else None
        self.client.upload_file(str(source), settings.S3_BUCKET, object_key, ExtraArgs=extra_args)

    @contextmanager
    def materialize(self, object_key: str) -> Iterator[Path]:
        """Download an object to temporary worker storage for the existing processors."""
        if settings.OBJECT_STORAGE_BACKEND == "filesystem":
            yield settings.STORAGE_DIR / object_key
            return

        suffix = Path(object_key).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary_file:
            local_path = Path(temporary_file.name)

        try:
            self.client.download_file(settings.S3_BUCKET, object_key, str(local_path))
            yield local_path
        finally:
            local_path.unlink(missing_ok=True)


def evidence_object_key(case_id: str, original_filename: str) -> str:
    """Generate an opaque, case-scoped S3 object key without trusting client paths."""
    import uuid

    safe_filename = Path(original_filename).name or "evidence"
    return f"cases/{case_id}/{uuid.uuid4()}_{safe_filename}"


object_storage = ObjectStorage()

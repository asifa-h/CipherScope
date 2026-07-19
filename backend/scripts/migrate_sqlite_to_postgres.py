"""One-time, explicit migration of Phase 1 SQLite data and evidence objects.

Run only after `alembic upgrade head` has created an empty PostgreSQL schema and
the configured MinIO bucket exists.  It intentionally refuses a non-empty
target database to avoid accidental duplicate imports.
"""

import argparse
import mimetypes
import sys
from pathlib import Path

import sqlalchemy as sa

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import Base, engine as target_engine
from app.services.object_storage import object_storage


TABLE_ORDER = ["organizations", "users", "cases", "evidence", "audit_logs"]


def _read_source(source_engine: sa.Engine) -> dict[str, list[dict]]:
    inspector = sa.inspect(source_engine)
    missing = set(TABLE_ORDER) - set(inspector.get_table_names())
    if missing:
        raise RuntimeError(f"SQLite source is missing required tables: {', '.join(sorted(missing))}")

    with source_engine.connect() as connection:
        return {
            table_name: [dict(row) for row in connection.execute(sa.select(Base.metadata.tables[table_name])).mappings()]
            for table_name in TABLE_ORDER
        }


def _upload_evidence(records: list[dict]) -> None:
    for record in records:
        source_path = Path(record["stored_path"])
        if not source_path.is_file():
            raise FileNotFoundError(
                f"Evidence {record['id']} refers to a missing file: {source_path}. "
                "Restore the legacy evidence directory before migrating."
            )

        filename = Path(record["original_filename"]).name or "evidence"
        object_key = f"cases/{record['case_id']}/{record['id']}/{filename}"
        content_type = record.get("mime_type") or mimetypes.guess_type(filename)[0]
        object_storage.upload_path(source_path, object_key, content_type)
        record["stored_path"] = object_key


def _write_target(records: dict[str, list[dict]]) -> None:
    organizations = Base.metadata.tables["organizations"]
    with target_engine.begin() as connection:
        existing_count = connection.execute(sa.select(sa.func.count()).select_from(organizations)).scalar_one()
        if existing_count:
            raise RuntimeError("Target PostgreSQL database is not empty; aborting to prevent a duplicate import.")

        for table_name in TABLE_ORDER:
            if records[table_name]:
                connection.execute(Base.metadata.tables[table_name].insert(), records[table_name])


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate CipherScope Phase 1 SQLite data to PostgreSQL and MinIO.")
    parser.add_argument("--sqlite-url", required=True, help="SQLAlchemy SQLite URL, e.g. sqlite:////backup/cipherscope.db")
    args = parser.parse_args()

    if not args.sqlite_url.startswith("sqlite"):
        parser.error("--sqlite-url must be a SQLite SQLAlchemy URL")

    source_engine = sa.create_engine(args.sqlite_url)
    records = _read_source(source_engine)
    _upload_evidence(records["evidence"])
    _write_target(records)
    print("SQLite data and evidence objects migrated successfully.")


if __name__ == "__main__":
    main()

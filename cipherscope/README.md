# CipherScope — Investigation Intelligence Platform

Phase 1 of the platform described in your project brief, built as a **case
management system** with the hierarchy:

```
Organization → Investigator (User) → Case → Evidence
```

This is real, working code — not a mockup. Every request below hits an actual
database, computes actual file hashes, and runs actual OCR / PDF text
extraction. Nothing is simulated.

## What's actually implemented (Phase 1)

- **Auth**: organization registration + JWT login (bcrypt-hashed passwords)
- **Cases**: create/list investigations, scoped per organization
- **Evidence upload**: streamed to disk, size-capped
- **Real SHA256 + MD5 hashing** of every uploaded file
- **Real OCR** on images via Tesseract (`pytesseract`), with per-file confidence score
- **Real PDF text-layer extraction** via `pypdf`
- **Plain text file reading** for `.txt` / `.csv` / `.log`
- **Duplicate detection** by SHA256 within a case
- **Audit log** table recording case/evidence events
- **Automated tests** (`pytest`) covering the whole pipeline, including
  cross-organization data isolation
- A frontend that talks to the real API — no mock data anywhere

## What's *not* built yet (by design — see roadmap below)

Video/audio AI (Whisper, speaker diarization, object detection), the
knowledge graph, semantic search, the LLM investigation chat, and the report
generator are **not implemented**. Building those for real requires GPU
inference or paid model APIs that need to run on infrastructure you provision
(a server, cloud GPU, or your own API keys) — they can't run inside this
sandbox. Phase 1 is architected so they slot in cleanly (see "Extending to
Phase 2+" below).

## Running it locally

### Option A — Docker (recommended)
```bash
docker compose up --build
```
API will be live at `http://localhost:8000`. Open `frontend/index.html`
directly in your browser (it talks to `http://localhost:8000` by default).

### Option B — Manual
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Tesseract is required for OCR — install the system binary:
#   macOS:  brew install tesseract
#   Ubuntu: apt-get install tesseract-ocr
#   Windows: https://github.com/UB-Mannheim/tesseract/wiki

uvicorn app.main:app --reload
```
Then open `frontend/index.html` in a browser.

### Running the tests
```bash
cd backend
pip install pytest httpx
pytest -v
```

## API quick reference

| Method | Path                                  | Purpose                        |
|--------|----------------------------------------|---------------------------------|
| POST   | `/auth/register`                       | Create org + first admin user  |
| POST   | `/auth/login`                          | Get a JWT                      |
| GET    | `/auth/me`                             | Current user                   |
| POST   | `/cases`                               | Create a case                  |
| GET    | `/cases`                               | List your org's cases          |
| GET    | `/cases/{id}`                          | Case detail                    |
| POST   | `/cases/{id}/evidence`                 | Upload + process a file        |
| GET    | `/cases/{id}/evidence`                 | List evidence for a case       |
| GET    | `/cases/{id}/evidence/{eid}`           | Evidence detail                |
| POST   | `/cases/{id}/evidence/{eid}/reprocess` | Re-run the extraction pipeline |

Interactive docs (Swagger) are auto-generated at `http://localhost:8000/docs`.

## Switching from SQLite to Postgres

Phase 1 defaults to SQLite for zero-setup local dev. To move to Postgres,
uncomment the `db` service in `docker-compose.yml` and set:
```
DATABASE_URL=postgresql+psycopg2://cipherscope:cipherscope@db:5432/cipherscope
```
No application code changes needed — SQLAlchemy handles the dialect switch.

## Extending to Phase 2+ (per your roadmap)

The codebase is deliberately modular so each phase is additive:

- **Phase 2 (Search, Chat, Citations)**: add a `vector_search.py` service
  (Qdrant/ChromaDB + embeddings) that indexes `Evidence.extracted_text` on
  save; add an `/investigations/{id}/ask` endpoint that does RAG restricted to
  that case's indexed evidence, with citations back to `evidence_id`.
- **Phase 3 (Timeline, Knowledge Graph)**: add `Entity` and `Relationship`
  tables (or a Neo4j sidecar) populated by an NER pass over `extracted_text`;
  a `timeline.py` service that orders evidence + extracted dates.
- **Phase 4 (Video/Audio AI)**: these are compute-heavy — move
  `process_evidence()` into a **Celery task** (Redis already sketched in
  `docker-compose.yml` comments) so uploads return immediately and processing
  happens in a worker. This is the one real architectural change Phase 1 was
  built to accommodate without a rewrite.
- **Phase 5 (Reports, Audit, Roles)**: `AuditLog` and `UserRole` already
  exist in the schema — a report generator just needs to query and render
  them (the `docx`/`pdf` skills in this environment can generate the actual
  export).

## Project structure
```
cipherscope/
├── backend/
│   ├── app/
│   │   ├── core/         # config, db session, JWT/password hashing, auth dependency
│   │   ├── models/        # SQLAlchemy models (Org, User, Case, Evidence, AuditLog)
│   │   ├── schemas/       # Pydantic request/response schemas
│   │   ├── routers/       # auth, cases, evidence endpoints
│   │   ├── services/      # evidence_processor.py — hashing/OCR/PDF pipeline
│   │   └── main.py
│   ├── tests/test_phase1.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/index.html    # real API calls, no mock data
└── docker-compose.yml
```

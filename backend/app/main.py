from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, cases, evidence

app = FastAPI(
    title="CipherScope API",
    description="Case Management & Investigation Intelligence Platform — Phase 1",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(evidence.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "cipherscope-api"}

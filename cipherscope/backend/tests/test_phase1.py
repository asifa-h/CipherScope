"""
Real integration tests against the FastAPI app using an isolated SQLite DB.
Run with:  pytest -v   (from the backend/ directory)
"""
import hashlib
import io
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_cipherscope.db"

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(scope="module")
def auth_headers():
    resp = client.post("/auth/register", json={
        "organization_name": "Test Org " + os.urandom(4).hex(),
        "full_name": "Test Investigator",
        "email": f"test_{os.urandom(4).hex()}@example.com",
        "password": "TestPass123!",
    })
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_register_and_me(auth_headers):
    resp = client.get("/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


def test_login_wrong_password():
    client.post("/auth/register", json={
        "organization_name": "WrongPassOrg " + os.urandom(4).hex(),
        "full_name": "X",
        "email": "wrongpass@example.com",
        "password": "CorrectPass123!",
    })
    resp = client.post("/auth/login", json={"email": "wrongpass@example.com", "password": "nope"})
    assert resp.status_code == 401


def test_create_case(auth_headers):
    resp = client.post("/cases", json={"title": "Test Case", "description": "desc"}, headers=auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["case_number"].startswith("CS-")
    assert body["evidence_count"] == 0


def test_upload_evidence_computes_real_hashes(auth_headers):
    case = client.post("/cases", json={"title": "Hash Test Case"}, headers=auth_headers).json()
    content = b"Hello CipherScope, this is a test evidence file."
    expected_sha256 = hashlib.sha256(content).hexdigest()
    expected_md5 = hashlib.md5(content).hexdigest()

    resp = client.post(
        f"/cases/{case['id']}/evidence",
        headers=auth_headers,
        files={"file": ("note.txt", io.BytesIO(content), "text/plain")},
    )
    assert resp.status_code == 201
    ev = resp.json()
    assert ev["sha256_hash"] == expected_sha256
    assert ev["md5_hash"] == expected_md5
    assert ev["status"] == "processed"
    assert ev["extracted_text"] == content.decode()
    assert ev["extraction_method"] == "plain_text_read"


def test_duplicate_detection(auth_headers):
    case = client.post("/cases", json={"title": "Dup Test Case"}, headers=auth_headers).json()
    content = b"duplicate content"

    first = client.post(
        f"/cases/{case['id']}/evidence", headers=auth_headers,
        files={"file": ("a.txt", io.BytesIO(content), "text/plain")},
    ).json()
    second = client.post(
        f"/cases/{case['id']}/evidence", headers=auth_headers,
        files={"file": ("b.txt", io.BytesIO(content), "text/plain")},
    ).json()

    assert second["is_duplicate_of"] == first["id"]
    assert second["sha256_hash"] == first["sha256_hash"]


def test_cross_org_case_isolation(auth_headers):
    other_org = client.post("/auth/register", json={
        "organization_name": "Other Org " + os.urandom(4).hex(),
        "full_name": "Other Investigator",
        "email": f"other_{os.urandom(4).hex()}@example.com",
        "password": "TestPass123!",
    }).json()
    other_headers = {"Authorization": f"Bearer {other_org['access_token']}"}

    mine = client.post("/cases", json={"title": "Private Case"}, headers=auth_headers).json()
    resp = client.get(f"/cases/{mine['id']}", headers=other_headers)
    assert resp.status_code == 404  # other org cannot see this case


def teardown_module(module):
    for f in ["test_cipherscope.db"]:
        if os.path.exists(f):
            os.remove(f)

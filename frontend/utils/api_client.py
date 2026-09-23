import os

import requests

# BACKEND_URL lets this work in both contexts without code changes:
# - Running locally (streamlit run streamlit_app.py, backend on your host) -> defaults to localhost:8000
# - Running in docker-compose -> set to http://backend:8000 (the service name), since
#   "localhost" inside a container refers to that container itself, never another one.
BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8000").strip().rstrip("/")
print(f"BACKEND_URL configured as: {BASE_URL}")
API_KEY = os.environ.get("API_KEY", "")


def _headers() -> dict:
    return {"X-API-Key": API_KEY} if API_KEY else {}


def upload_document(file_bytes: bytes, filename: str, content_type: str) -> dict:
    resp = requests.post(
        f"{BASE_URL}/documents/",
        files={"file": (filename, file_bytes, content_type)},
        headers=_headers(),
    )
    resp.raise_for_status()
    return resp.json()


def trigger_review(document_id: str) -> dict:
    resp = requests.post(f"{BASE_URL}/documents/{document_id}/review", headers=_headers())
    resp.raise_for_status()
    return resp.json()


def get_report(document_id: str) -> dict:
    resp = requests.get(f"{BASE_URL}/documents/{document_id}/report", headers=_headers())
    resp.raise_for_status()
    return resp.json()


def get_document(document_id: str) -> dict:
    resp = requests.get(f"{BASE_URL}/documents/{document_id}", headers=_headers())
    resp.raise_for_status()
    return resp.json()


def list_documents() -> list[dict]:
    resp = requests.get(f"{BASE_URL}/documents/", headers=_headers())
    resp.raise_for_status()
    return resp.json()

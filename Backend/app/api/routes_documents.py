from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.auth import verify_api_key
from app.db import crud
from app.db.database import get_db
from app.parsing.clause_segmenter import segment_clauses
from app.parsing.doc_parser import extract_text
from app.schemas.document_schema import DocumentOut, DocumentUploadResponse

router = APIRouter(prefix="/documents", tags=["documents"], dependencies=[Depends(verify_api_key)])
SUPPORTED_TYPES = {".pdf", ".docx", ".txt"}


@router.post("/", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_TYPES:
        raise HTTPException(400, f"Unsupported file type: {suffix}. Use .pdf, .docx, or .txt")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    raw_text = extract_text(tmp_path)
    clauses = segment_clauses(raw_text)

    doc = crud.create_document(db, filename=file.filename, raw_text=raw_text)
    crud.save_clauses(db, doc.id, clauses)
    doc.status = "parsed"
    db.commit()

    return DocumentUploadResponse(document_id=doc.id, clause_count=len(clauses))


@router.get("/", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    return crud.list_documents(db)


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, db: Session = Depends(get_db)):
    doc = crud.get_document(db, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc
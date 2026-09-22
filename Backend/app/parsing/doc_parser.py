from __future__ import annotations

from pathlib import Path

import pdfplumber
from docx import Document as DocxDocument


def extract_text(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return _extract_pdf(file_path)
    if ext == ".docx":
        return _extract_docx(file_path)
    if ext == ".txt":
        return Path(file_path).read_text()
    raise ValueError(f"Unsupported file type: {ext}. Supported: .pdf, .docx, .txt")


def _extract_pdf(file_path: str) -> str:
    with pdfplumber.open(file_path) as pdf:
        return "\n\n".join(page.extract_text() or "" for page in pdf.pages)


def _extract_docx(file_path: str) -> str:
    doc = DocxDocument(file_path)
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
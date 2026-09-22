"""
ORM tables. Mirrors the Pydantic state models but adds what persistence needs
(timestamps, foreign keys).

RegulationSection is separate from Finding: it's a static, human-curated
corpus of DPDP Act / IT Act text (seeded via app/ingestion/load_regulations.py),
searched by core/regulations.py to ground compliance_agent's findings in real
statute text. Nothing the pipeline generates ever gets written back into this
table — it's read-only from the agents' point of view, which is what keeps it
from turning into a self-reinforcing loop of past (possibly wrong) findings.
"""
from __future__ import annotations

import datetime
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

COHERE_EMBED_DIM = 1024  # embed-english-v3.0 output size


def _uuid() -> str:
    return str(uuid.uuid4())


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String)
    raw_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="uploaded")  # uploaded|parsing|reviewing|done|failed
    uploaded_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    clauses: Mapped[list["Clause"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    report: Mapped["Report"] = relationship(back_populates="document", uselist=False, cascade="all, delete-orphan")


class Clause(Base):
    __tablename__ = "clauses"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    clause_number: Mapped[int] = mapped_column()
    heading: Mapped[str | None] = mapped_column(String, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    start_char: Mapped[int | None] = mapped_column(nullable=True)
    end_char: Mapped[int | None] = mapped_column(nullable=True)

    document: Mapped["Document"] = relationship(back_populates="clauses")
    findings: Mapped[list["Finding"]] = relationship(back_populates="clause", cascade="all, delete-orphan")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    clause_id: Mapped[str] = mapped_column(ForeignKey("clauses.id"))
    agent: Mapped[str] = mapped_column(String)          # risk | compliance | ambiguity
    severity: Mapped[str] = mapped_column(String)        # low | medium | high | critical
    issue: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    approved: Mapped[bool] = mapped_column(default=False)

    clause: Mapped["Clause"] = relationship(back_populates="findings")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), unique=True)
    overall_score: Mapped[int] = mapped_column()
    overall_risk: Mapped[str] = mapped_column(String)
    summary: Mapped[str] = mapped_column(Text)
    top_issues: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    document: Mapped["Document"] = relationship(back_populates="report")


class RegulationSection(Base):
    """Static corpus of DPDP Act / IT Act text, seeded once via ingestion.
    Read-only from the pipeline's perspective — compliance_agent retrieves
    from this, nothing ever writes back into it."""
    __tablename__ = "regulation_sections"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    section: Mapped[str] = mapped_column(String)   # e.g. "DPDP Act 2023, Section 8(6)"
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(Vector(COHERE_EMBED_DIM))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.state import ClauseState, FindingState, GraphState
from app.db.models import Clause, Document, Finding, Report


def create_document(db: Session, filename: str, raw_text: str) -> Document:
    doc = Document(filename=filename, raw_text=raw_text)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def save_clauses(db: Session, document_id: str, clauses: list[ClauseState]) -> list[Clause]:
    rows = [
        Clause(
            id=c.clause_id, document_id=document_id, clause_number=c.clause_number,
            heading=c.heading, text=c.text, start_char=c.start_char, end_char=c.end_char,
        )
        for c in clauses
    ]
    db.add_all(rows)
    db.commit()
    return rows


def save_findings(db: Session, findings: list[FindingState]) -> list[Finding]:
    rows = [
        Finding(
            id=f.finding_id, clause_id=f.clause_id, agent=f.agent.value, severity=f.severity.value,
            issue=f.issue, recommendation=f.recommendation, confidence=f.confidence, approved=f.approved,
        )
        for f in findings
    ]
    db.add_all(rows)
    db.commit()
    return rows


def save_report(db: Session, document_id: str, report: dict) -> Report:
    row = Report(
        document_id=document_id,
        overall_score=report.get("overall_score", 0),
        overall_risk=report.get("overall_risk", "unknown"),
        summary=report.get("summary", ""),
        top_issues=report.get("top_issues", []),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def save_graph_state(db: Session, document_id: str, state: GraphState) -> None:
    """Persists a completed pipeline run: clauses, findings, and final report in one go."""
    save_clauses(db, document_id, state.clauses)
    save_findings(db, state.findings)
    if state.final_report:
        save_report(db, document_id, state.final_report)


def get_document(db: Session, document_id: str) -> Document | None:
    return db.get(Document, document_id)


def list_documents(db: Session, limit: int = 50) -> list[Document]:
    return db.query(Document).order_by(Document.uploaded_at.desc(),  Document.id.desc()).limit(limit).all()


def get_findings_for_document(db: Session, document_id: str) -> list[Finding]:
    return (
        db.query(Finding)
        .join(Clause, Finding.clause_id == Clause.id)
        .filter(Clause.document_id == document_id)
        .all()
    )
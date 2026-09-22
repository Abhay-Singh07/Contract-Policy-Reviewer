from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.orchestrator import build_graph
from app.core.auth import verify_api_key
from app.core.state import ClauseState, GraphState
from app.db import crud
from app.db.database import get_db
from app.schemas.finding_schema import FindingOut
from app.schemas.report_schema import ReportOut

router = APIRouter(prefix="/documents", tags=["review"], dependencies=[Depends(verify_api_key)])


@router.post("/{document_id}/review", response_model=ReportOut)
def trigger_review(document_id: str, db: Session = Depends(get_db)):
    doc = crud.get_document(db, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    if not doc.clauses:
        raise HTTPException(400, "Document has no parsed clauses to review")

    clause_states = [
        ClauseState(clause_id=c.id, clause_number=c.clause_number, heading=c.heading,
                    text=c.text, start_char=c.start_char, end_char=c.end_char)
        for c in doc.clauses
    ]

    doc.status = "reviewing"
    db.commit()

    graph = build_graph(db)
    result = graph.invoke(GraphState(document_id=doc.id, clauses=clause_states))

    crud.save_findings(db, result["findings"])
    report_row = crud.save_report(db, doc.id, result["final_report"])
    doc.status = "done"
    db.commit()

    findings = crud.get_findings_for_document(db, doc.id)
    return ReportOut(
        overall_score=report_row.overall_score, overall_risk=report_row.overall_risk,
        summary=report_row.summary, top_issues=report_row.top_issues,
        findings=[FindingOut.model_validate(f) for f in findings],
    )


@router.get("/{document_id}/report", response_model=ReportOut)
def get_report(document_id: str, db: Session = Depends(get_db)):
    doc = crud.get_document(db, document_id)
    if not doc or not doc.report:
        raise HTTPException(404, "No report yet — has review been triggered for this document?")

    findings = crud.get_findings_for_document(db, document_id)
    return ReportOut(
        overall_score=doc.report.overall_score, overall_risk=doc.report.overall_risk,
        summary=doc.report.summary, top_issues=doc.report.top_issues,
        findings=[FindingOut.model_validate(f) for f in findings],
    )
from datetime import timedelta

from app.core.state import AgentType, ClauseState, FindingState, GraphState, Severity
from app.db import crud


def _clause() -> ClauseState:
    return ClauseState(clause_number=1, heading="Indemnity",
                        text="The Vendor shall indemnify the Client against all claims, without limit.")


def test_create_document(db):
    doc = crud.create_document(db, filename="sample_nda.pdf", raw_text="some text")
    assert doc.id is not None
    assert doc.filename == "sample_nda.pdf"
    assert doc.status == "uploaded"


def test_save_graph_state_round_trip(db):
    clauses = [_clause()]
    doc = crud.create_document(db, filename="sample_nda.pdf", raw_text=clauses[0].text)

    state = GraphState(document_id=doc.id, clauses=clauses)
    state.findings.append(FindingState(
        clause_id=clauses[0].clause_id, agent=AgentType.RISK, severity=Severity.HIGH,
        issue="Uncapped indemnity.", recommendation="Add a liability cap.", confidence=0.9, approved=True,
    ))
    state.final_report = {"overall_score": 62, "overall_risk": "high",
                           "summary": "Uncapped indemnity is a concern.", "top_issues": ["Uncapped indemnity"]}

    crud.save_graph_state(db, doc.id, state)

    fetched = crud.get_document(db, doc.id)
    findings = crud.get_findings_for_document(db, doc.id)

    assert fetched.filename == "sample_nda.pdf"
    assert len(findings) == 1
    assert findings[0].issue == "Uncapped indemnity."
    assert fetched.report.overall_score == 62
    assert fetched.report.overall_risk == "high"


def test_list_documents_orders_newest_first(db):
    first = crud.create_document(
        db,
        filename="first.pdf",
        raw_text="a",
    )

    second = crud.create_document(
        db,
        filename="second.pdf",
        raw_text="b",
    )

    # Explicitly control timestamps so the test is deterministic.
    second.uploaded_at = first.uploaded_at + timedelta(seconds=1)
    db.commit()

    docs = crud.list_documents(db)

    assert docs[0].filename == "second.pdf"
    assert docs[1].filename == "first.pdf"


def test_get_document_returns_none_for_unknown_id(db):
    assert crud.get_document(db, "does-not-exist") is None


def test_get_findings_for_document_only_returns_that_documents_findings(db):
    doc_a = crud.create_document(db, filename="a.pdf", raw_text="text a")
    doc_b = crud.create_document(db, filename="b.pdf", raw_text="text b")

    clause_a = ClauseState(clause_number=1, text="clause in doc a")
    clause_b = ClauseState(clause_number=1, text="clause in doc b")
    crud.save_clauses(db, doc_a.id, [clause_a])
    crud.save_clauses(db, doc_b.id, [clause_b])

    finding_a = FindingState(clause_id=clause_a.clause_id, agent=AgentType.RISK,
                              severity=Severity.LOW, issue="issue a", recommendation="fix a")
    finding_b = FindingState(clause_id=clause_b.clause_id, agent=AgentType.RISK,
                              severity=Severity.LOW, issue="issue b", recommendation="fix b")
    crud.save_findings(db, [finding_a, finding_b])

    findings_for_a = crud.get_findings_for_document(db, doc_a.id)

    assert len(findings_for_a) == 1
    assert findings_for_a[0].issue == "issue a"
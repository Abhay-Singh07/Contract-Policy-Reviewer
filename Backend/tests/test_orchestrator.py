from unittest.mock import patch

from app.agents.orchestrator import build_graph
from app.core.embeddings import get_embedding_client
from app.core.state import ClauseState, GraphState
from app.db.models import RegulationSection


class ScriptedLLMClient:
    """Fakes agent behaviour by peeking at the system prompt's first words, and
    tracks whether each agent type ever saw regulation-grounding context — so
    tests can assert only compliance gets it.
    qa_review rejects the Indemnity clause's first pass on purpose, to prove
    the requeue loop actually fires and reruns the specialists.
    """
    def __init__(self):
        self.qa_calls_per_clause: dict[str, int] = {}
        self.risk_saw_grounding = False
        self.compliance_saw_grounding = False
        self.ambiguity_saw_grounding = False
        self.compliance_call_count = 0

    def generate_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> dict:
        grounded = "Relevant regulation text" in user_prompt

        if "risk analyst" in system_prompt:
            self.risk_saw_grounding = self.risk_saw_grounding or grounded
            return {"findings": [{
                "issue": "Uncapped indemnity exposes Vendor to unlimited liability.",
                "recommendation": "Cap indemnity at total fees paid.",
                "severity": "high", "confidence": 0.9,
            }]} if "Indemnity" in user_prompt else {"findings": []}

        if "compliance analyst" in system_prompt:
            self.compliance_call_count += 1
            self.compliance_saw_grounding = self.compliance_saw_grounding or grounded
            return {"findings": []}

        if "drafting reviewer" in system_prompt:  # ambiguity
            self.ambiguity_saw_grounding = self.ambiguity_saw_grounding or grounded
            return {"findings": []}

        if "quality reviewer" in system_prompt:  # qa_agent
            clause_key = user_prompt.split("\n")[0]
            n = self.qa_calls_per_clause.get(clause_key, 0) + 1
            self.qa_calls_per_clause[clause_key] = n
            if n == 1 and "Indemnity" in user_prompt:
                return {"decisions": [{"index": 0, "approved": False}], "needs_requeue": True}
            return {"decisions": [{"index": 0, "approved": True}], "needs_requeue": False}

        if "final reviewer" in system_prompt:  # judge
            return {
                "overall_score": 62, "overall_risk": "high",
                "summary": "Uncapped indemnity is the main issue.",
                "top_issues": ["Uncapped indemnity clause"],
            }
        return {}


def _seed_regulation(db):
    embed_client = get_embedding_client()
    text = "The Data Fiduciary shall notify the Board and affected Data Principals of any data breach."
    vec = embed_client.embed([text])[0]
    db.add(RegulationSection(section="DPDP Act 2023, Section 8(6)", text=text, embedding=vec))
    db.flush()


def test_orchestrator_runs_full_pipeline_and_grounds_only_compliance(db):
    _seed_regulation(db)
    scripted = ScriptedLLMClient()
    clauses = [
        ClauseState(clause_number=1, heading="Termination",
                    text="Either party may terminate this agreement with 7 days notice."),
        ClauseState(clause_number=2, heading="Indemnity",
                    text="The Vendor shall indemnify the Client against all claims, without limit."),
    ]

    with patch("app.agents.orchestrator.get_llm_client", return_value=scripted):
        graph = build_graph(db)
        result = graph.invoke(GraphState(document_id="doc-test", clauses=clauses))

    assert len(result["findings"]) == 1
    assert result["findings"][0].approved is True
    assert result["final_report"]["overall_score"] == 62

    assert scripted.compliance_saw_grounding is True
    assert scripted.risk_saw_grounding is False
    assert scripted.ambiguity_saw_grounding is False


def test_requeue_loop_actually_reruns_specialists(db):
    _seed_regulation(db)
    scripted = ScriptedLLMClient()
    clauses = [ClauseState(clause_number=1, heading="Indemnity",
                            text="The Vendor shall indemnify the Client against all claims, without limit.")]

    with patch("app.agents.orchestrator.get_llm_client", return_value=scripted):
        graph = build_graph(db)
        graph.invoke(GraphState(document_id="doc-test-2", clauses=clauses))

    # qa_agent was called twice for the same clause: rejected first, approved second
    calls = list(scripted.qa_calls_per_clause.values())
    assert calls == [2]


def test_requeue_respects_max_requeues_safety_valve(db):
    """If qa_review keeps rejecting forever, the graph must still terminate."""
    _seed_regulation(db)

    class AlwaysRejectLLM:
        def generate_json(self, system_prompt, user_prompt, temperature=0.2):
            if "risk analyst" in system_prompt:
                return {"findings": [{"issue": "x", "recommendation": "y", "severity": "low", "confidence": 0.5}]}
            if "compliance analyst" in system_prompt or "drafting reviewer" in system_prompt:
                return {"findings": []}
            if "quality reviewer" in system_prompt:
                return {"decisions": [{"index": 0, "approved": False}], "needs_requeue": True}
            if "final reviewer" in system_prompt:
                return {"overall_score": 50, "overall_risk": "medium", "summary": "test", "top_issues": []}
            return {}

    clause = ClauseState(clause_number=1, text="A clause that never satisfies qa_review.")

    with patch("app.agents.orchestrator.get_llm_client", return_value=AlwaysRejectLLM()):
        graph = build_graph(db)
        # must complete without hanging or raising, even though qa never approves
        result = graph.invoke(GraphState(document_id="doc-test-3", clauses=[clause], max_requeues=2))

    assert result["final_report"] is not None


def test_compliance_llm_never_called_when_no_regulation_matches(db):
    """Cost optimization: with zero regulations seeded, no clause should ever
    trigger a compliance LLM call — the embedding lookup already told us there's
    nothing relevant, so we shouldn't spend a Groq call confirming that."""
    scripted = ScriptedLLMClient()
    clauses = [ClauseState(clause_number=1, heading="Notices",
                            text="Any notice under this Agreement shall be sent by courier or email.")]

    # deliberately do NOT seed any RegulationSection rows

    with patch("app.agents.orchestrator.get_llm_client", return_value=scripted):
        graph = build_graph(db)
        graph.invoke(GraphState(document_id="doc-test-4", clauses=clauses))

    assert scripted.compliance_call_count == 0


def test_default_max_requeues_is_one():
    """Cost optimization: default requeue budget lowered from 2 to 1."""
    state = GraphState(document_id="doc-test-5", clauses=[])
    assert state.max_requeues == 1
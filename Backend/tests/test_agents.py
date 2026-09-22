from app.agents import compliance_agent, judge_agent, qa_agent, risk_agent
from app.core.llm_client import MockLLMClient
from app.core.state import AgentType, FindingState, Severity


def test_risk_agent_parses_findings(indemnity_clause):
    llm = MockLLMClient({"findings": [{
        "issue": "Uncapped indemnity.", "recommendation": "Add a cap.",
        "severity": "high", "confidence": 0.9,
    }]})
    findings = risk_agent.run(indemnity_clause, llm)

    assert len(findings) == 1
    assert findings[0].agent == AgentType.RISK
    assert findings[0].severity == Severity.HIGH
    assert findings[0].approved is False  # nothing approves it yet — that's qa_agent's job


def test_specialist_skips_malformed_findings(indemnity_clause):
    llm = MockLLMClient({"findings": [{"issue": "missing severity and recommendation"}]})
    findings = risk_agent.run(indemnity_clause, llm)
    assert findings == []


def test_compliance_agent_forwards_regulation_context(indemnity_clause):
    captured = {}

    class SpyLLM:
        def generate_json(self, system_prompt, user_prompt, temperature=0.2):
            captured["user_prompt"] = user_prompt
            return {"findings": []}

    compliance_agent.run(indemnity_clause, SpyLLM(), regulation_context="Relevant regulation text: DPDP Section 8(6)")
    assert "Relevant regulation text" in captured["user_prompt"]


def test_compliance_agent_prompt_unchanged_with_no_context(indemnity_clause):
    captured = {}

    class SpyLLM:
        def generate_json(self, system_prompt, user_prompt, temperature=0.2):
            captured["user_prompt"] = user_prompt
            return {"findings": []}

    compliance_agent.run(indemnity_clause, SpyLLM())  # no regulation_context passed
    assert "Relevant regulation text" not in captured["user_prompt"]


def test_qa_agent_sets_approval_and_can_trigger_requeue(indemnity_clause):
    findings = risk_agent.run(indemnity_clause, MockLLMClient({"findings": [{
        "issue": "x", "recommendation": "y", "severity": "high", "confidence": 0.9,
    }]}))
    llm = MockLLMClient({"decisions": [{"index": 0, "approved": False}], "needs_requeue": True})

    reviewed, needs_requeue = qa_agent.run(indemnity_clause, findings, llm)

    assert needs_requeue is True
    assert reviewed[0].approved is False


def test_qa_agent_with_no_findings_never_requeues(indemnity_clause):
    reviewed, needs_requeue = qa_agent.run(indemnity_clause, [], MockLLMClient())
    assert reviewed == []
    assert needs_requeue is False


def test_judge_aggregates_only_approved_findings():
    approved = FindingState(clause_id="c1", agent=AgentType.RISK, severity=Severity.HIGH,
                             issue="approved issue", recommendation="fix", approved=True)
    rejected = FindingState(clause_id="c1", agent=AgentType.RISK, severity=Severity.LOW,
                             issue="rejected issue", recommendation="fix", approved=False)
    llm = MockLLMClient({"overall_score": 62, "overall_risk": "high",
                          "summary": "test summary", "top_issues": ["approved issue"]})

    report = judge_agent.run([approved, rejected], llm)

    assert report["finding_count"] == 1
    assert report["overall_score"] == 62


def test_judge_with_no_approved_findings_short_circuits_without_llm_call():
    report = judge_agent.run([], MockLLMClient())
    assert report["overall_score"] == 100
    assert report["overall_risk"] == "low"
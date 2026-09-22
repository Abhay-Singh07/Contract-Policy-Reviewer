from __future__ import annotations
import json

from app.agents.prompts.qa_prompt import QA_SYSTEM_PROMPT
from app.core.llm_client import LLMClient
from app.core.state import ClauseState, FindingState


def run(clause: ClauseState, findings: list[FindingState], llm: LLMClient) -> tuple[list[FindingState], bool]:
    """Reviews findings raised for one clause. Returns (findings_with_approval_set, needs_requeue)."""
    if not findings:
        return findings, False

    findings_payload = [
        {"issue": f.issue, "recommendation": f.recommendation, "severity": f.severity.value, "agent": f.agent.value}
        for f in findings
    ]
    user_prompt = (
        f'Clause #{clause.clause_number} ("{clause.heading or "Untitled"}"):\n{clause.text}\n\n'
        f"Findings to review:\n{json.dumps(findings_payload, indent=2)}"
    )
    result = llm.generate_json(QA_SYSTEM_PROMPT, user_prompt)

    decisions = {d["index"]: d.get("approved", False) for d in result.get("decisions", [])}
    for i, finding in enumerate(findings):
        finding.approved = decisions.get(i, False)

    return findings, bool(result.get("needs_requeue", False))
from __future__ import annotations

import json

from app.agents.prompts.judge_prompt import JUDGE_SYSTEM_PROMPT
from app.core.llm_client import LLMClient
from app.core.state import FindingState


def run(findings: list[FindingState], llm: LLMClient) -> dict:
    """Aggregates all approved findings across the whole document into a final report dict."""
    approved = [f for f in findings if f.approved]
    if not approved:
        return {
            "overall_score": 100, "overall_risk": "low",
            "summary": "No material issues were found in this contract.", "top_issues": [],
        }

    payload = [
        {"clause_id": f.clause_id, "agent": f.agent.value, "severity": f.severity.value, "issue": f.issue}
        for f in approved
    ]
    user_prompt = f"Approved findings across the document:\n{json.dumps(payload, indent=2)}"
    report = llm.generate_json(JUDGE_SYSTEM_PROMPT, user_prompt)
    report["finding_count"] = len(approved)
    return report
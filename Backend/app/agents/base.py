from __future__ import annotations

from app.core.llm_client import LLMClient
from app.core.state import AgentType, ClauseState, FindingState, Severity


def run_specialist(
    agent: AgentType,
    system_prompt: str,
    clause: ClauseState,
    llm: LLMClient,
    extra_context: str = "",
) -> list[FindingState]:
    """Call the LLM with a specialist prompt on one clause, parse into FindingState objects.

    extra_context is optional retrieved context to append to the prompt — currently only
    compliance_agent passes anything here (relevant DPDP/IT Act text from core/regulations.py).
    Risk and ambiguity call this with no extra_context; see orchestrator.py's module docstring
    for why retrieval isn't wired into them.

    Malformed entries from the model are skipped rather than crashing the pipeline —
    a bad JSON field shouldn't take down the whole review.
    """
    user_prompt = f'Clause #{clause.clause_number} ("{clause.heading or "Untitled"}"):\n{clause.text}'
    if extra_context:
        user_prompt += f"\n\n{extra_context}"
    result = llm.generate_json(system_prompt, user_prompt)

    findings: list[FindingState] = []
    for raw in result.get("findings", []):
        try:
            findings.append(FindingState(
                clause_id=clause.clause_id,
                agent=agent,
                severity=Severity(raw["severity"]),
                issue=raw["issue"],
                recommendation=raw["recommendation"],
                confidence=float(raw.get("confidence", 0.7)),
            ))
        except (KeyError, ValueError):
            continue  # skip malformed finding rather than failing the whole clause
    return findings
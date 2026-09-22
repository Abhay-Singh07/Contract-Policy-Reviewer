from app.agents.base import run_specialist
from app.agents.prompts.compliance_prompt import COMPLIANCE_SYSTEM_PROMPT
from app.core.llm_client import LLMClient
from app.core.state import AgentType, ClauseState, FindingState


def run(clause: ClauseState, llm: LLMClient, regulation_context: str = "") -> list[FindingState]:
    return run_specialist(AgentType.COMPLIANCE, COMPLIANCE_SYSTEM_PROMPT, clause, llm, regulation_context)
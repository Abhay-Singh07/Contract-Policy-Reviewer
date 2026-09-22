from app.agents.base import run_specialist
from app.agents.prompts.ambiguity_prompt import AMBIGUITY_SYSTEM_PROMPT
from app.core.llm_client import LLMClient
from app.core.state import AgentType, ClauseState, FindingState


def run(clause: ClauseState, llm: LLMClient) -> list[FindingState]:
    return run_specialist(AgentType.AMBIGUITY, AMBIGUITY_SYSTEM_PROMPT, clause, llm)
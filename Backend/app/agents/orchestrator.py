"""
LangGraph wiring for the review pipeline. Mirrors the diagram exactly:

    dispatch_specialists -> qa_review --(needs_requeue)--> dispatch_specialists
                                       --(else)------------> advance_clause
    advance_clause --(more clauses)--> dispatch_specialists
                   --(all done)------> judge -> END

RAG note: only compliance_agent gets retrieval, from the static regulation
corpus (core/regulations.py) — risk and ambiguity run on clause text alone.
Nothing the pipeline generates is written back anywhere, so there's no
feedback loop where a wrong finding could keep reinforcing itself.
build_graph() takes `db` (needed for the regulation lookup), so nodes are
built as closures inside it rather than as bare module-level functions.
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agents import ambiguity_agent, compliance_agent, judge_agent, qa_agent, risk_agent
from app.config import settings
from app.core.llm_client import get_llm_client
from app.core.regulations import find_relevant_regulations, format_regulation_context
from app.core.state import GraphState

# ---- Conditional routing (no DB needed, stay module-level) -----------------


def route_after_qa(state: GraphState) -> str:
    return "requeue" if state.needs_requeue else "proceed"


def route_after_advance(state: GraphState) -> str:
    return "done" if state.is_done else "next"


# ---- Graph assembly ----------------------------------------------------------


def build_graph(db: Session):
    """Builds the compiled graph, binding `db` into dispatch_specialists via closure
    (it's the only node that needs one, for the regulation lookup)."""

    def dispatch_specialists(state: GraphState) -> GraphState:
        """Runs risk + compliance + ambiguity agents on the current clause.
        Only compliance gets retrieval context — see module docstring for why."""
        clause = state.current_clause
        if clause is None:
            return state

        llm = get_llm_client()
        regulation_context = format_regulation_context(find_relevant_regulations(db, clause.text, top_k=3))

        # On a requeue, drop this clause's earlier findings first so rejected
        # ones don't linger alongside the fresh batch.
        state.findings = [f for f in state.findings if f.clause_id != clause.clause_id]

        state.findings.extend(risk_agent.run(clause, llm))

        # Cost fix #1: skip the compliance LLM call entirely if nothing relevant
        # was retrieved. No regulation match means this clause almost certainly
        # isn't a DPDP/IT Act issue — the embedding lookup already told us that
        # cheaply, no need to spend a full Groq call confirming it.
        if regulation_context:
            state.findings.extend(compliance_agent.run(clause, llm, regulation_context))

        # Cost fix #2: ambiguity detection is a simpler task than risk/compliance
        # reasoning, so it runs on a cheaper/faster model.
        ambiguity_llm = get_llm_client(model=settings.GROQ_AMBIGUITY_MODEL)
        state.findings.extend(ambiguity_agent.run(clause, ambiguity_llm))

        return state

    def qa_review(state: GraphState) -> GraphState:
        """Self-critiques this clause's findings, decides approve/reject + requeue."""
        clause = state.current_clause
        if clause is None:
            state.needs_requeue = False
            return state

        llm = get_llm_client()
        clause_findings = [f for f in state.findings if f.clause_id == clause.clause_id]
        _, needs_requeue = qa_agent.run(clause, clause_findings, llm)

        # Safety valve: never loop forever on one clause.
        if needs_requeue and state.requeue_count >= state.max_requeues:
            needs_requeue = False

        state.needs_requeue = needs_requeue
        state.requeue_count = state.requeue_count + 1 if needs_requeue else 0
        return state

    def advance_clause(state: GraphState) -> GraphState:
        state.current_index += 1
        state.requeue_count = 0
        return state

    def judge(state: GraphState) -> GraphState:
        llm = get_llm_client()
        state.final_report = judge_agent.run(state.findings, llm)
        return state

    graph = StateGraph(GraphState)

    graph.add_node("dispatch_specialists", dispatch_specialists)
    graph.add_node("qa_review", qa_review)
    graph.add_node("advance_clause", advance_clause)
    graph.add_node("judge", judge)

    graph.set_entry_point("dispatch_specialists")
    graph.add_edge("dispatch_specialists", "qa_review")

    graph.add_conditional_edges(
        "qa_review",
        route_after_qa,
        {"requeue": "dispatch_specialists", "proceed": "advance_clause"},
    )
    graph.add_conditional_edges(
        "advance_clause",
        route_after_advance,
        {"done": "judge", "next": "dispatch_specialists"},
    )
    graph.add_edge("judge", END)

    return graph.compile()
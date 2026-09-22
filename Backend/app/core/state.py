"""
Core state models for the contract-reviewer LangGraph pipeline.

These three models are the backbone of the whole system:
- ClauseState  -> one clause of the contract
- FindingState -> one issue an agent (risk/compliance/ambiguity) raised about a clause
- GraphState   -> the full LangGraph state passed between nodes
"""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentType(str, Enum):
    RISK = "risk"
    COMPLIANCE = "compliance"
    AMBIGUITY = "ambiguity"


class ClauseState(BaseModel):
    """One segmented clause from the uploaded document."""
    clause_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    clause_number: int                     # order in the document, 1-indexed
    heading: Optional[str] = None          # e.g. "Termination", "Indemnity"
    text: str
    start_char: Optional[int] = None       # offset in original doc (for highlighting in UI)
    end_char: Optional[int] = None


class FindingState(BaseModel):
    """One issue raised by a specialist agent about a clause."""
    finding_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    clause_id: str
    agent: AgentType
    severity: Severity
    issue: str                             # what's wrong
    recommendation: str                    # suggested fix
    confidence: float = Field(ge=0.0, le=1.0, default=0.7)
    approved: bool = False                 # set True by qa_agent after self-critique


class GraphState(BaseModel):
    """The full state LangGraph threads through every node."""
    document_id: str
    clauses: list[ClauseState]
    current_index: int = 0                 # which clause we're currently on
    findings: list[FindingState] = Field(default_factory=list)

    # qa_review -> advance_clause loop control (see the diagram)
    needs_requeue: bool = False
    requeue_count: int = 0
    max_requeues: int = 1                  # safety valve so a clause can't loop forever

    final_report: Optional[dict] = None    # filled in by judge_agent at the end

    @property
    def current_clause(self) -> Optional[ClauseState]:
        if 0 <= self.current_index < len(self.clauses):
            return self.clauses[self.current_index]
        return None

    @property
    def is_done(self) -> bool:
        return self.current_index >= len(self.clauses)
"""
Finds DPDP Act / IT Act sections relevant to a clause, via pgvector's cosine
distance operator. Unlike the old memory.py design, this corpus is static —
seeded once by app/ingestion/load_regulations.py — and nothing the pipeline
generates is ever written back into it. That's deliberate: it removes the
feedback loop where a wrongly-approved finding could get archived and then
keep influencing future findings toward repeating the same mistake.

Only compliance_agent uses this. Risk and ambiguity don't get retrieval:
risk judgments are too deal-specific for a generic "standard clause" to be a
safe anchor, and ambiguity is about this clause's specific wording, not
precedent. See project discussion for the full reasoning.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.embeddings import get_embedding_client
from app.db.models import RegulationSection

# Cosine distance is 0 (identical) to 2 (opposite). Anything above this is
# treated as "not actually relevant" rather than padding the prompt with
# noise just to hit top_k.
MAX_RELEVANT_DISTANCE = 0.6


def find_relevant_regulations(db: Session, clause_text: str, top_k: int = 3) -> list[RegulationSection]:
    embed_client = get_embedding_client()
    query_vector = embed_client.embed([clause_text])[0]

    distance = RegulationSection.embedding.cosine_distance(query_vector)
    return (
        db.query(RegulationSection)
        .filter(distance < MAX_RELEVANT_DISTANCE)
        .order_by(distance)
        .limit(top_k)
        .all()
    )


def format_regulation_context(sections: list[RegulationSection]) -> str:
    """Turns retrieved statute sections into a prompt block. Phrased as
    authoritative — unlike the old finding-based memory, this is actual law
    text, not a past AI guess, so compliance_agent can cite it directly."""
    if not sections:
        return ""
    lines = ["Relevant regulation text (cite these directly where applicable):"]
    for s in sections:
        lines.append(f"- {s.section}: {s.text}")
    return "\n".join(lines)
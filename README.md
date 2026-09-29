# Contract Reviewer

Multi-agent AI system for reviewing contracts against Indian law — the **Digital Personal Data Protection Act (DPDP) 2023** and the **Information Technology Act, 2000**. Upload a contract, and specialist agents independently review it for risk, regulatory compliance, and drafting ambiguity, with a self-critique loop and a final aggregated report.

**Live demo:** [Streamlit app](https://contract-policy-reviewer.streamlit.app/)

---

## Overview

A contract is parsed into clauses, and each clause is run through three independent specialist agents before a judge produces a final report:
             ┌──────────────┐
    ┌───────▶│ dispatch_    │◀────────────┐
    │        │ specialists  │              │
    │        └──────┬───────┘              │
    │               │                      │
    │     (risk + compliance + ambiguity    │
    │      run on the current clause)       │
    │               ▼                      │
    │        ┌──────────────┐              │
    │        │  qa_review    │              │
    │        └──────┬───────┘              │
    │               │                       │
    │     needs_requeue?  ── yes ───────────┘
    │               │ no
    │               ▼
    │        ┌──────────────┐
    └────────│ advance_clause│
              └──────┬───────┘
                     │
          more clauses? ── yes ──▶ (back to dispatch_specialists)
                     │ no
                     ▼
              ┌──────────────┐
              │    judge      │
              └──────┬───────┘
                     ▼
                    END


- **`dispatch_specialists`** runs three independent agents on the current clause: **risk**, **compliance**, and **ambiguity**.
- **`qa_review`** self-critiques the findings just raised — approving, rejecting, or (within a capped retry budget) sending the clause back for another pass.
- **`judge`** aggregates every approved finding across the document into a final score, risk level, and summary.

## Design decisions worth knowing

A few choices here were deliberate, not defaults:

- **Deterministic, sequential dispatch — not LLM-driven tool calling.** The orchestrator always calls all three specialists in a fixed order; the model never decides on its own what to check. For a compliance tool, predictable and auditable behavior matters more than letting an LLM freely choose what to inspect.
- **RAG only for the compliance agent.** Risk assessment is too deal-specific for a generic "standard clause" to be a safe reference point, and ambiguity is about a clause's own wording, not precedent — so only compliance is grounded in retrieved regulation text.
- **No self-writing memory.** An earlier design let approved findings feed back into future retrieval — and got removed. A wrongly-approved finding could become "precedent" that reinforces itself across reviews. The compliance corpus is now a static, human-curated set of DPDP Act / IT Act excerpts, seeded once and never written to by the pipeline.
- **Three separate specialist agents, not one combined call.** Merging risk/compliance/ambiguity into a single LLM call would cut token cost, but the point of this project is to demonstrate a genuine multi-agent architecture — so the split stays, and cost is managed elsewhere instead (see below).
- **Cost controls that don't collapse the architecture:**
  - Skip the compliance LLM call entirely when nothing relevant is retrieved from the regulation corpus (verified with a test asserting zero calls, not just zero grounding).
  - Ambiguity detection runs on a smaller/faster model (`llama-3.1-8b-instant`) than risk/compliance (`llama-3.3-70b-versatile`), since it's a simpler task.
  - Requeue budget capped at 1 retry per clause.
  - All four agent prompts carry an explicit materiality bar — early versions returned ~100 findings on a 14-clause contract; tightening "only flag material issues" language cut that down substantially.

## Tech stack

| Layer | Tech |
|---|---|
| Orchestration | LangGraph |
| LLM | Groq (LLaMA 3.3 70B for risk/compliance, LLaMA 3.1 8B Instant for ambiguity) |
| Embeddings | Cohere |
| Database | PostgreSQL + pgvector ([Neon](https://neon.tech) in production) |
| Backend | FastAPI, deployed on AWS Lambda via the [AWS Lambda Web Adapter](https://github.com/awslabs/aws-lambda-web-adapter) |
| Frontend | Streamlit ([Streamlit Community Cloud](https://streamlit.io/cloud) in production) |
| ORM / migrations | SQLAlchemy + Alembic |
| Testing | pytest, against a dedicated disposable test database |

## Testing

```bash
cd backend
pytest -v
```

Tests run against a dedicated `<db>_test` database, created and torn down automatically — never against real data. Migration correctness (not just application logic) is also covered: a separate test suite runs the actual `alembic upgrade`/`downgrade` commands against a disposable database, since the main suite's fast schema setup bypasses Alembic entirely and wouldn't catch a broken migration.

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check (no auth required) |
| `POST` | `/documents/` | Upload a `.pdf` / `.docx` / `.txt` contract |
| `GET` | `/documents/` | List previously uploaded documents |
| `GET` | `/documents/{id}` | Get a document and its parsed clauses |
| `POST` | `/documents/{id}/review` | Run the full multi-agent review pipeline |
| `GET` | `/documents/{id}/report` | Get the final report for a reviewed document |

All routes except `/health` require an `X-API-Key` header.

## Deployment

Deployed entirely within free-tier limits:

- **Backend** — Docker image on Amazon ECR Public → AWS Lambda (via Lambda Web Adapter, so the FastAPI app runs largely unmodified) → exposed through a Lambda Function URL (no API Gateway).
- **Database** — [Neon](https://neon.tech) serverless PostgreSQL with pgvector.
- **Frontend** — Streamlit Community Cloud.

## Known limitations

- Upload size is capped by Lambda's 6MB synchronous payload limit.
- The regulation corpus is a curated subset of DPDP Act / IT Act sections, not the full text of either act.
- No user accounts — access is gated by a single shared API key.


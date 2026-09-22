from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_documents, routes_health, routes_review

app = FastAPI(title="Contract Reviewer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this before deploying anywhere real
    allow_methods=["*"],
    allow_headers=["*"],
)

# Schema creation is now handled by Alembic (`alembic upgrade head`), run once
# per environment before the app starts — not implicit on every server boot.
# See alembic/README or run `alembic upgrade head` from backend/.

app.include_router(routes_health.router)
app.include_router(routes_documents.router)
app.include_router(routes_review.router)
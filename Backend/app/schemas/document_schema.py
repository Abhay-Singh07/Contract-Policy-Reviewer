import datetime

from pydantic import BaseModel, ConfigDict


class ClauseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    clause_number: int
    heading: str | None
    text: str


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    status: str
    uploaded_at: datetime.datetime
    clauses: list[ClauseOut] = []


class DocumentUploadResponse(BaseModel):
    document_id: str
    clause_count: int
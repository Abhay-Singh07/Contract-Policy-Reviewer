from pydantic import BaseModel, ConfigDict


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    clause_id: str
    agent: str
    severity: str
    issue: str
    recommendation: str
    confidence: float
    approved: bool
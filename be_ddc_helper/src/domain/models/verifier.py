from pydantic import BaseModel, Field


class VerifierResult(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    feedback: str

from pydantic import BaseModel


class SectionCommand(BaseModel):
    command_id: str
    dealer_id: str
    section_type: str
    position: int


class SectionResult(BaseModel):
    command_id: str
    success: bool
    error: str | None = None

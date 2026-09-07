import uuid

from pydantic import BaseModel

from app.schemas.document import SourceOut


class AgentRequest(BaseModel):
    conversation_id: uuid.UUID | None = None
    message: str
    image_id: uuid.UUID | None = None


class AgentToolCallOut(BaseModel):
    tool: str
    input: dict
    output: dict | list | str


class AgentResponse(BaseModel):
    conversation_id: uuid.UUID
    answer: str
    tool_calls: list[AgentToolCallOut]
    sources: list[SourceOut] = []

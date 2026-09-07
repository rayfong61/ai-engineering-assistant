import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    file_size: int | None = None
    status: str
    created_at: datetime


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID | None = None
    message: str


class SourceOut(BaseModel):
    document_id: uuid.UUID
    filename: str
    page: int | None
    content: str


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    answer: str
    sources: list[SourceOut]


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class MessageSourceOut(BaseModel):
    document_id: uuid.UUID
    filename: str
    page: int | None


class MessageImageOut(BaseModel):
    image_id: uuid.UUID
    filename: str
    url: str | None = None  # None on signing failure, matches VisionAnalysisOut.image_url


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    sources: list[MessageSourceOut] | None = None
    image: MessageImageOut | None = None


class ConversationDetailOut(ConversationOut):
    messages: list[MessageOut]

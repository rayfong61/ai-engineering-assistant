import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EmailPreviewRequest(BaseModel):
    instruction: str
    conversation_id: uuid.UUID | None = None


class EmailSendRequest(BaseModel):
    email_log_id: uuid.UUID


class EmailLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recipient: str | None
    subject: str | None
    body: str | None
    status: str
    created_at: datetime

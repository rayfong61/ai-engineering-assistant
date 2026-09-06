import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ActivityLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    user_id: uuid.UUID
    event_type: str
    detail: str | None
    created_at: datetime

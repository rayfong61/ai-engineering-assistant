import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VisionAnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    analysis: str
    observations: list[str]
    limitations: list[str]
    created_at: datetime
    image_url: str | None = None

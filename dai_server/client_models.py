"""DAI server shared response models."""

from pydantic import BaseModel


class CommitResponse(BaseModel):
    success: bool
    decision_id: str | None = None
    record_hash: str | None = None
    error: str | None = None

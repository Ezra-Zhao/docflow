"""Job model and lifecycle states.

State machine: queued -> processing -> done | failed
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_job_id() -> str:
    return uuid.uuid4().hex[:12]


class Job(SQLModel, table=True):
    id: str = Field(default_factory=new_job_id, primary_key=True)
    filename: str
    ext: str  # pdf | docx | txt | png | jpg | jpeg | gif | webp | bmp | tiff
    status: JobStatus = Field(default=JobStatus.QUEUED, index=True)
    error: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

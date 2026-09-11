from enum import StrEnum
from typing import Annotated, Literal

from fastapi import UploadFile
from pydantic import BaseModel, StringConstraints

# The calling service owns the job id and sends it as a CUID; we never mint one.
# Loose enough for both cuid ("c" + 24 chars) and cuid2 (2-32 chars): a
# lowercase letter followed by lowercase alphanumerics.
CUID_PATTERN = r"^[a-z][a-z0-9]{1,31}$"
CUID = Annotated[str, StringConstraints(pattern=CUID_PATTERN)]


class JobStatus(StrEnum):
  PENDING = "PENDING"
  IN_PROGRESS = "IN_PROGRESS"
  COMPLETED = "COMPLETED"
  FAILED = "FAILED"


class JobStart(BaseModel):
  job_id: CUID
  material: str
  amount: int
  action: Literal["extract", "baseline", "part", "structure", "setup", "ready", "article"] = "baseline"
  article_number: Annotated[str, StringConstraints(pattern=r"^[0-9]{8}$")] | None = None


class JobStartForm(JobStart):
  """Multipart flavour of `JobStart`, carrying the drawing to work from.

  The upload has to live on the model itself: FastAPI only flattens a form
  model into separate fields when it is the single body parameter.
  """

  drawing: UploadFile | None = None


class JobCreated(BaseModel):
  job_id: CUID


class JobStatusUpdate(BaseModel):
  """Posted to the other app on every status transition."""

  job_id: CUID
  status: JobStatus

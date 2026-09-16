from dataclasses import dataclass, field

from api.schema import CUID, JobStatus, JobStatusUpdate


class DuplicateJobError(RuntimeError):
  """Raised when the other app reuses a job id we already know about."""


@dataclass(slots=True)
class JobStatusStore:
  data: dict[CUID, JobStatusUpdate] = field(default_factory=dict)

  def create(self, job_id: CUID, status: JobStatus = JobStatus.PENDING) -> None:
    if job_id in self.data:
      raise DuplicateJobError("Job with specified ID already exists!")
    self.data[job_id] = JobStatusUpdate(job_id=job_id, status=status)

  def get_status_by_id(self, job_id: CUID) -> JobStatusUpdate | None:
    return self.data.get(job_id)

  def update_status(self, job_id: CUID, status: JobStatus) -> None:
    if job_id not in self.data:
      raise RuntimeError("Job with specified ID does not exist!")
    self.data[job_id].status = status

  def update(self, update: JobStatusUpdate) -> None:
    self.data[update.job_id] = update

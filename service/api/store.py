from dataclasses import dataclass, field

from api.schema import CUID, JobStatus


class DuplicateJobError(RuntimeError):
  """Raised when the other app reuses a job id we already know about."""


@dataclass(slots=True)
class JobStatusStore:
  data: dict[CUID, JobStatus] = field(default_factory=dict)

  def create(self, job_id: CUID, status: JobStatus = JobStatus.PENDING) -> None:
    if job_id in self.data:
      raise DuplicateJobError("Job with specified ID already exists!")
    self.data = {**self.data, job_id: status}

  def get_status_by_id(self, job_id: CUID) -> JobStatus | None:
    return self.data.get(job_id)

  def update_status(self, job_id: CUID, status: JobStatus) -> None:
    if job_id not in self.data:
      raise RuntimeError("Job with specified ID does not exist!")
    self.data = {**self.data, job_id: status}

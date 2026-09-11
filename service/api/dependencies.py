import asyncio
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from api.config import NXWorkerConfig, StorageConfig
from api.drawings import DrawingStore
from api.schema import CUID, JobStart
from api.store import JobStatusStore


@dataclass(frozen=True, slots=True)
class Job:
  """A single unit of work handed over to the worker."""

  start: JobStart
  drawing_path: Path | None = None

  @property
  def job_id(self) -> CUID:
    """The id the other app gave us; the only one anything here refers to."""
    return self.start.job_id


@dataclass(slots=True)
class JobQueue:
  """In-memory FIFO queue between the API and the single worker.

  Queue state is not persisted, so anything still queued is lost on restart.
  """

  _queue: asyncio.Queue[Job] = field(default_factory=asyncio.Queue)

  async def put(self, job: Job) -> None:
    await self._queue.put(job)

  async def get(self) -> Job:
    return await self._queue.get()

  def task_done(self) -> None:
    self._queue.task_done()

# The store and the queue only mean something as long as they are shared by
# every request and the worker, hence the cached singletons.
@lru_cache(maxsize=1)
def get_job_status_store() -> JobStatusStore:
  return JobStatusStore()


@lru_cache(maxsize=1)
def get_job_queue() -> JobQueue:
  return JobQueue()


@lru_cache(maxsize=1)
def get_nx_worker_config() -> NXWorkerConfig:
  return NXWorkerConfig()


@lru_cache(maxsize=1)
def get_drawing_store() -> DrawingStore:
  return DrawingStore(directory=StorageConfig().data_dir)

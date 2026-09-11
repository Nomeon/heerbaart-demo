import asyncio
import logging
from dataclasses import dataclass, field

import pipeline
from api.config import WorkerConfig
from api.dependencies import Job, JobQueue
from api.notifier import NXWorkerNotifier
from api.schema import CUID, JobStatus
from api.store import JobStatusStore

logger = logging.getLogger(__name__)


async def run_nx_job(job: Job) -> None:
  """Run the pipeline; its returned paths stay on the NX server."""
  logger.info("running NX job %s (%s)", job.job_id, job.start.action)
  await pipeline.run_job(
    job.start.action,
    drawing_path=job.drawing_path,
    article_number=job.start.article_number,
    job_id=job.job_id,
  )


@dataclass(slots=True)
class JobWorker:
  """The single, non-concurrent consumer of the job queue.

  Exactly one instance is started in the app lifespan and it awaits each job
  to completion before pulling the next one, so the NX routine never runs
  twice at the same time.
  """

  queue: JobQueue
  store: JobStatusStore
  notifier: NXWorkerNotifier
  config: WorkerConfig = field(default_factory=WorkerConfig)

  async def supervise(self) -> None:
    """Run the loop, and put it back on its feet if it ever falls over.

    `run` already survives a failing job; this only covers the loop itself
    dying, in which case the job it was holding is lost.
    """
    delay = self.config.restart_delay_seconds
    while True:
      try:
        await self.run()
      except asyncio.CancelledError:
        raise
      except Exception:
        logger.exception("worker loop died, restarting in %ss", delay)
        await asyncio.sleep(delay)

  async def run(self) -> None:
    while True:
      job = await self.queue.get()
      try:
        await self._process(job)
      except Exception:
        logger.exception("unexpected failure while handling job %s", job.job_id)
      finally:
        self.queue.task_done()

  async def _process(self, job: Job) -> None:
    try:
      await self._report(job.job_id, JobStatus.PENDING)
      await self._report(job.job_id, JobStatus.IN_PROGRESS)
      await run_nx_job(job)
    except Exception:
      logger.exception("NX job %s (%s) failed", job.job_id, job.start.action)
      await self._report(job.job_id, JobStatus.FAILED)
      return

    await self._report(job.job_id, JobStatus.COMPLETED)

  async def _report(self, job_id: CUID, status: JobStatus) -> None:
    self.store.update_status(job_id, status)
    try:
      await self.notifier.send_status(job_id, status)
    except Exception:
      logger.exception("status callback failed for %s: %s", job_id, status)

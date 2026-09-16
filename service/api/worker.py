import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pipeline
from api.config import WorkerConfig
from api.dependencies import Job, JobQueue
from api.notifier import NXWorkerNotifier
from api.schema import JobStatus, JobStatusUpdate
from api.store import JobStatusStore

logger = logging.getLogger(__name__)


async def run_nx_job(job: Job, progress=None) -> dict:
  """Run the pipeline and return its outcome to the app."""
  logger.info("running NX job %s (%s)", job.job_id, job.start.action)
  return await pipeline.run_job(
    job.start.action,
    drawing_path=job.drawing_path,
    article_number=job.start.article_number,
    job_id=job.job_id,
    material=job.start.material,
    amount=job.start.amount,
    progress=progress,
    resume_from=job.start.resume_from,
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
    update = JobStatusUpdate(job_id=job.job_id, status=JobStatus.PENDING)

    async def progress(stage, workflow):
      update.status = JobStatus.IN_PROGRESS
      update.stage = stage
      update.workflow = workflow
      update.stage_started_at = datetime.now(timezone.utc)
      await self._report(update)

    try:
      await self._report(update)
      await progress(job.start.resume_from if job.start.action == "retry_article" else "family_check",
                     "article" if job.start.action in {"approve_baseline_and_generate", "retry_article"} else "baseline")
      result = await run_nx_job(job, progress)
      update.outcome = result.get("outcome")
      update.setup_path = result.get("setup")
      update.workflow = result.get("workflow", update.workflow)
    except Exception as exc:
      logger.exception("NX job %s (%s) failed", job.job_id, job.start.action)
      update.status = JobStatus.FAILED
      update.error = str(exc) or type(exc).__name__
      await self._report(update)
      return

    update.status = JobStatus.COMPLETED
    await self._report(update)

  async def _report(self, update: JobStatusUpdate) -> None:
    self.store.update(update.model_copy())
    try:
      await self.notifier.send_status(**update.model_dump())
    except Exception:
      logger.exception("status callback failed for %s: %s", update.job_id, update.status)

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, status

from api.config import LoggingConfig
from api.dependencies import (
  Job,
  JobQueue,
  get_drawing_store,
  get_job_queue,
  get_job_status_store,
  get_nx_worker_config,
)
from api.drawings import DrawingStore, RequestSizeLimit
from api.notifier import NXWorkerNotifier
from api.schema import (
  CUID,
  JobCreated,
  JobStart,
  JobStartForm,
  JobStatus,
  JobStatusUpdate,
)
from api.store import DuplicateJobError, JobStatusStore
from api.worker import JobWorker

_logging = LoggingConfig()
logging.basicConfig(level=_logging.level, format=_logging.format)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
  notifier = NXWorkerNotifier(config=get_nx_worker_config())
  worker = JobWorker(
    queue=get_job_queue(),
    store=get_job_status_store(),
    notifier=notifier,
  )
  # One worker task, and only one: that is what keeps the jobs from
  # overlapping. `supervise` restarts the loop if it ever falls over.
  task = asyncio.create_task(worker.supervise(), name="nx-job-worker")
  try:
    yield
  finally:
    task.cancel()
    with suppress(asyncio.CancelledError):
      await task
    await notifier.aclose()


app = FastAPI(lifespan=lifespan)
app.add_middleware(RequestSizeLimit)


@app.get("/")
async def root():
  return {"service": "Elster Rev.D NX POC"}


@app.post("/start/nx-job", status_code=status.HTTP_201_CREATED)
async def start_nx_job(
  form: Annotated[JobStartForm, Form()],
  status_store: Annotated[JobStatusStore, Depends(get_job_status_store)],
  queue: Annotated[JobQueue, Depends(get_job_queue)],
  drawing_store: Annotated[DrawingStore, Depends(get_drawing_store)],
) -> JobCreated:
  """Queue an NX job under the CUID the caller sent in.

  Every status update comes back tagged with that id; results stay local.
  """
  if form.action in {"extract", "baseline", "prepare_quotation"} and form.drawing is None:
    raise HTTPException(status_code=422, detail=f"drawing is required for {form.action}")
  if form.action in {"article", "prepare_quotation", "approve_baseline_and_generate", "retry_article"} and form.article_number is None:
    raise HTTPException(status_code=422, detail="article_number is required for article")
  if form.action == "retry_article" and form.resume_from is None:
    raise HTTPException(status_code=422, detail="resume_from is required for retry_article")

  job_id = form.job_id
  # Claim the id first, so a replay does not overwrite a drawing or queue the
  # same job twice.
  try:
    status_store.create(job_id, JobStatus.PENDING)
  except DuplicateJobError as exc:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

  drawing_path = None
  if form.action in {"extract", "baseline", "prepare_quotation"}:
    try:
      drawing_path = await drawing_store.save(job_id, form.drawing)
    except Exception as exc:
      logger.exception("saving drawing for NX job %s (%s) failed", job_id, form.action)
      status_store.update_status(job_id, JobStatus.FAILED)
      if isinstance(exc, HTTPException):
        raise
      raise HTTPException(status_code=500, detail="Failed to save drawing") from exc

  await queue.put(
    Job(
      start=JobStart(
        job_id=job_id,
        material=form.material,
        amount=form.amount,
        action=form.action,
        article_number=form.article_number,
        resume_from=form.resume_from,
      ),
      drawing_path=drawing_path,
    )
  )
  return JobCreated(job_id=job_id)


@app.get("/jobs/{job_id}")
async def get_job_status(
  job_id: CUID,
  status_store: Annotated[JobStatusStore, Depends(get_job_status_store)],
) -> JobStatusUpdate:
  status = status_store.get_status_by_id(job_id)
  if status is None:
    raise HTTPException(status_code=404, detail="Unknown job id")
  return status

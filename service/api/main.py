import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from fastapi import Path as PathParameter
from pipeline import family_directory
from nc_release import released_nc
from drawing_analysis import analyze_drawing

from api.config import LoggingConfig
from api.dependencies import (
  Job,
  JobQueue,
  get_drawing_store,
  get_job_queue,
  get_job_status_store,
  get_nx_worker_config,
)
from api.drawings import DrawingStore, RequestSizeLimit, MAX_ANALYSIS_BYTES
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


@app.post("/drawings/analyze")
async def analyze_uploaded_drawing(drawing: Annotated[UploadFile, File()]):
  """Read the article choices without queueing NX or creating a family."""
  try:
    if not (drawing.filename or "").lower().endswith(".pdf"):
      raise HTTPException(status_code=422, detail="Select a PDF drawing")
    with TemporaryDirectory(prefix="elster-analysis-") as directory:
      path = Path(directory) / "drawing.pdf"
      size = 0
      with path.open("wb") as output:
        while chunk := await drawing.read(1024 * 1024):
          if size == 0 and not chunk.startswith(b"%PDF-"):
            raise HTTPException(status_code=422, detail="Select a valid PDF drawing")
          size += len(chunk)
          if size > MAX_ANALYSIS_BYTES:
            raise HTTPException(status_code=413, detail="Drawing exceeds 25 MiB")
          output.write(chunk)
      if size == 0:
        raise HTTPException(status_code=422, detail="Select a valid PDF drawing")
      table = await analyze_drawing(path, family_directory())
      return {"articleNumbers": [row.article_number for row in table.articles]}
  except HTTPException:
    raise
  except Exception as exc:
    logger.exception("Elster drawing analysis failed")
    raise HTTPException(status_code=422, detail="Could not read the Elster drawing") from exc
  finally:
    await drawing.close()


@app.get("/articles/{article_number}/nc")
async def get_article_nc(article_number: Annotated[str, PathParameter(pattern=r"^[0-9]{8}$")]):
  output = released_nc(family_directory() / article_number, article_number)
  if output is None:
    raise HTTPException(status_code=409, detail="NC program has not passed external simulation")
  return FileResponse(output, media_type="application/octet-stream", filename=output.name,
                      headers={"Cache-Control": "no-store"})


@app.get("/articles/{article_number}/setup-sheet")
async def get_article_setup_sheet(article_number: Annotated[str, PathParameter(pattern=r"^[0-9]{8}$")]):
  item_dir = family_directory() / article_number
  output = item_dir / f"{article_number}_INSTELBLAD.pdf"
  if released_nc(item_dir, article_number) is None or not output.is_file():
    raise HTTPException(status_code=409, detail="Setup sheet is not available")
  return FileResponse(output, media_type="application/pdf", filename=output.name,
                      headers={"Cache-Control": "no-store"})


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

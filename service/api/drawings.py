import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile
from starlette.responses import JSONResponse

from api.schema import CUID

logger = logging.getLogger(__name__)

MAX_DRAWING_BYTES = 32 * 1024 * 1024
MAX_ANALYSIS_BYTES = 25 * 1024 * 1024


class RequestSizeLimit:
  """Cap bytes before multipart parsing can spool an unlimited upload to disk."""

  def __init__(self, app):
    self.app = app

  async def __call__(self, scope, receive, send):
    if scope["type"] != "http" or scope["path"] not in {"/start/nx-job", "/drawings/analyze"}:
      return await self.app(scope, receive, send)
    limit = (MAX_ANALYSIS_BYTES if scope["path"] == "/drawings/analyze" else MAX_DRAWING_BYTES) + 1024 * 1024
    length = dict(scope.get("headers", [])).get(b"content-length")
    if length and length.isdigit() and int(length) > limit:
      response = JSONResponse({"detail": "Drawing upload is too large"}, status_code=413)
      return await response(scope, receive, send)
    size = 0

    async def limited_receive():
      nonlocal size
      message = await receive()
      size += len(message.get("body", b""))
      if size > limit:
        raise HTTPException(status_code=413, detail="Drawing upload is too large")
      return message

    await self.app(scope, limited_receive, send)


@dataclass(slots=True)
class DrawingStore:
  """Keeps uploaded drawings on disk under server-selected paths."""

  directory: Path

  async def save(self, job_id: CUID, drawing: UploadFile) -> Path:
    path = self.directory / "uploads" / job_id / "drawing.pdf"

    def write() -> None:
      path.parent.mkdir(parents=True, exist_ok=True)
      size = 0
      try:
        with path.open("wb") as output:
          while chunk := drawing.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_DRAWING_BYTES:
              raise HTTPException(status_code=413, detail="Drawing exceeds 32 MiB")
            output.write(chunk)
      except Exception:
        path.unlink(missing_ok=True)
        raise

    # Copy the spooled upload in bounded chunks without blocking the event loop.
    await asyncio.to_thread(write)
    logger.info("saved drawing for job %s to %s", job_id, path)
    return path

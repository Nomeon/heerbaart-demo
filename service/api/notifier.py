import json
import logging
from dataclasses import dataclass, field

import httpx

from api.config import NXWorkerConfig
from api.schema import CUID, JobStatus, JobStatusUpdate

logger = logging.getLogger(__name__)

# A response body is only ever logged as a hint about what the other app made
# of the call, so there is no point keeping all of it.
MAX_RESPONSE_CHARS = 500


def _snippet(text: str) -> str:
  text = text.strip()
  if len(text) <= MAX_RESPONSE_CHARS:
    return text
  return f"{text[:MAX_RESPONSE_CHARS]}... ({len(text)} chars)"


@dataclass(slots=True)
class NXWorkerNotifier:
  """Reports job status back to the other app.

  A callback that fails is logged and swallowed: the job itself already ran,
  so failing to announce it should not take the worker down.
  """

  config: NXWorkerConfig
  client: httpx.AsyncClient = field(init=False)

  def __post_init__(self) -> None:
    self.client = httpx.AsyncClient(
      base_url=self.config.base_url,
      headers=self.config.headers,
      timeout=self.config.timeout_seconds,
    )

  async def send_status(self, job_id: CUID, status: JobStatus) -> None:
    path = self.config.status_path
    body = JobStatusUpdate(job_id=job_id, status=status).model_dump(mode="json")
    url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
    # Everything that leaves here gets logged, both what we sent and what
    # came back. Headers stay out of it: they carry the API key.
    logger.info("--> POST %s %s", url, json.dumps(body, default=str))
    try:
      response = await self.client.post(path, json=body)
      response.raise_for_status()
    except httpx.HTTPError as exc:
      logger.warning("<-- POST %s failed: %s", url, exc, exc_info=True)
      return
    logger.info("<-- POST %s %s %s", url, response.status_code, _snippet(response.text))

  async def aclose(self) -> None:
    await self.client.aclose()

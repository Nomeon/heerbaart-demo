import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

# Load the .env before any config object reads the environment. Variables that
# are already set in the process environment
# win over the file, so this only fills in the blanks. Point `ENV_FILE` at
# another file to use it instead.
# Look next to wherever the app was started from first, then next to this
# file, so it also works when uvicorn is run from another directory.
_env_file = os.environ.get("ENV_FILE") or find_dotenv(usecwd=True) or find_dotenv()
if _env_file:
  load_dotenv(_env_file)


@dataclass(frozen=True, slots=True)
class NXWorkerConfig:
  """Where the NX worker reports back to.

  Each field defaults to a value suited to a local callback app and is
  otherwise taken from the environment or .env.
  """

  base_url: str = field(
    default_factory=lambda: os.environ.get("NX_CALLBACK_URL", "http://localhost:8001")
  )
  api_key: str = field(
    default_factory=lambda: os.environ.get("NX_CALLBACK_API_KEY", "")
  )
  status_path: str = field(
    default_factory=lambda: os.environ.get("NX_CALLBACK_STATUS_PATH", "/jobs/status")
  )
  timeout_seconds: float = field(
    default_factory=lambda: float(os.environ.get("NX_CALLBACK_TIMEOUT", "10"))
  )

  @property
  def headers(self) -> dict[str, str]:
    return {"X-API-Key": self.api_key} if self.api_key else {}


@dataclass(frozen=True, slots=True)
class LoggingConfig:
  """Logging for the app's own loggers.

  Uvicorn only configures its own, so without this the notifier's INFO lines
  never make it to the console.
  """

  level: str = field(
    default_factory=lambda: os.environ.get("NX_LOG_LEVEL", "INFO").upper()
  )
  format: str = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


@dataclass(frozen=True, slots=True)
class StorageConfig:
  """Local pipeline data, including uploads; gitignored, without automatic cleanup."""

  data_dir: Path = field(
    default_factory=lambda: Path(os.environ.get("NX_DATA_DIR", "data"))
  )


@dataclass(frozen=True, slots=True)
class WorkerConfig:
  """Knobs for the single job worker."""

  restart_delay_seconds: float = field(
    default_factory=lambda: float(os.environ.get("NX_WORKER_RESTART_DELAY", "1"))
  )

import os

import uvicorn

from api.config import LoggingConfig

if __name__ == "__main__":
  uvicorn.run(
    "api.main:app",
    host=os.environ.get("NX_HOST", "127.0.0.1"),
    port=int(os.environ.get("NX_PORT", "9009")),
    log_level=LoggingConfig().level.lower(),
    workers=1,
    reload=False,
  )

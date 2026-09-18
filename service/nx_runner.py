"""Run one headless NX journal at a time, using the laptop's NX installation."""

import asyncio
import json
import logging
import math
import os
from pathlib import Path
import sys
import tempfile


PROJECT_DIR = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)


def custom_directory() -> Path:
  return Path(os.environ.get(
    "NX_CUSTOM_DIR", "C:/Heerbaart/NX2512_Custom/NX2512_Custom"
  )).resolve()


def _environment(install: Path, custom: Path, request_file: Path, result_file: Path,
                 *, stage: str | None = None) -> dict[str, str]:
  nxbin = install / "NXBIN"
  # CSE loads NX's bundled Python. Use that same runtime for its NXOpen journal.
  home = (nxbin / "python" if stage == "simulation" else
          Path(os.environ.get("NX_PYTHON_HOME") or sys.prefix)).resolve()
  library = custom / "MACH" / "resource" / "library"
  python_paths = [
    home, home / "DLLs", home / "Lib", home / "Lib" / "site-packages",
    nxbin / "python", PROJECT_DIR,
  ]
  if stage == "simulation":
    python_paths = [home, home / "Python312.zip", PROJECT_DIR]
  library_paths = {
    "UGII_CAM_LIBRARY_DIR": library,
    "UGII_CAM_LIBRARY_MACHINE_DIR": library / "machine",
    "UGII_CAM_LIBRARY_MACHINE_ASCII_DIR": library / "machine" / "ascii",
    "UGII_CAM_LIBRARY_MACHINE_DATA_DIR": library / "machine" / "ascii",
    "UGII_CAM_LIBRARY_INSTALLED_MACHINES_DIR": library / "machine" / "installed_machines",
    "UGII_CAM_LIBRARY_MACHINE_GRAPHICS_PATH": library / "machine" / "installed_machines",
    "UGII_CAM_LIBRARY_DEVICE_DIR": library / "device",
    "UGII_CAM_LIBRARY_DEVICE_DATA_DIR": library / "device" / "ascii",
    "UGII_CAM_LIBRARY_DEVICE_ASCII_DIR": library / "device" / "ascii",
    "UGII_CAM_LIBRARY_DEVICE_GRAPHICS_PATH": library / "device" / "graphics",
  }
  if stage == "simulation" and os.environ.get("NX_SIMULATION_CUSTOM_DIR"):
    # Match the working interactive CSE kit without changing article references,
    # assembly libraries or the postprocessor used by the other stages.
    simulation_library = Path(os.environ["NX_SIMULATION_CUSTOM_DIR"]) / "MACH" / "resource" / "library"
    library_paths["UGII_CAM_LIBRARY_INSTALLED_MACHINES_DIR"] = simulation_library / "machine" / "installed_machines"
    library_paths["UGII_CAM_LIBRARY_TOOL_GRAPHICS_PATH"] = simulation_library / "tool" / "graphics"
  return {
    **{key: value for key, value in os.environ.items()
       if key not in {"OPENAI_API_KEY", "NX_CALLBACK_API_KEY"}},
    **{key: str(path) + os.sep for key, path in library_paths.items()},
    "UGII_BASE_DIR": str(install),
    "NXBIN": str(nxbin),
    "NX_ENABLE_HEADLESS_GRAPHICS": "1",
    "UGII_ENV_FILE": str(custom / "UGII" / "ugii_env.dat"),
    "UGII_PYTHON_LIBRARY_DIR": str(home),
    "UGII_PYTHON_HOME": str(home),
    "UGII_PYTHON_DLL": "python312.dll",
    "UGII_PYTHONPATH": os.pathsep.join(map(str, python_paths)),
    "PATH": os.pathsep.join([
      str(nxbin), str(home), str(home / "Library" / "bin"), str(home / "DLLs"),
      os.environ.get("PATH", ""),
    ]),
    "HEERBAART_NX_REQUEST": str(request_file),
    "HEERBAART_NX_RESULT": str(result_file),
  }


async def _stop_process(process) -> None:
  if process.returncode is None:
    # run_journal can own child processes; do not leave them running after shutdown.
    killer = await asyncio.create_subprocess_exec(
      "taskkill", "/PID", str(process.pid), "/T", "/F",
      stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    await killer.wait()
    if process.returncode is None:
      try:
        process.kill()
      except ProcessLookupError:
        pass
  await process.wait()


async def run_nx(stage: str, request: dict, work_root: Path) -> dict:
  if os.name != "nt":
    raise RuntimeError("NX stages run on the Windows NX laptop, not this platform")
  if stage == "setup_sheet":
    from setup_sheet_runner import run_setup_sheet
    return await run_setup_sheet(request, work_root)
  timeout = float(os.environ.get("NX_JOURNAL_TIMEOUT", "900"))
  if not math.isfinite(timeout) or timeout <= 0:
    raise ValueError("NX_JOURNAL_TIMEOUT must be a finite positive number of seconds")
  custom = custom_directory()
  install = Path(os.environ.get(
    "NX_INSTALL_DIR", "C:/Program Files/Siemens/DesigncenterNX2512"
  )).resolve()
  executable = install / "NXBIN" / "run_journal.exe"
  if not executable.is_file():
    raise FileNotFoundError(f"NX journal runner not found: {executable}")
  work_root.mkdir(parents=True, exist_ok=True)
  work_dir = Path(tempfile.mkdtemp(prefix=stage + "_", dir=work_root)).resolve()
  request_file = work_dir / "request.json"
  result_file = work_dir / "result.json"
  log_file = work_dir / "nx.log"
  request_file.write_text(json.dumps({
    **request, "stage": stage, "work_dir": str(work_dir),
    "custom_dir": str(custom),
  }, indent=2), encoding="utf-8")
  logger.info("NX %s starting; log: %s", stage, log_file)
  with log_file.open("wb") as log:
    process = await asyncio.create_subprocess_exec(
      str(executable), str(PROJECT_DIR / "nx" / "entry.py"),
      cwd=PROJECT_DIR, env=_environment(install, custom, request_file, result_file, stage=stage),
      stdout=log, stderr=asyncio.subprocess.STDOUT,
    )
    try:
      code = await asyncio.wait_for(process.wait(), timeout=timeout)
    except (TimeoutError, asyncio.CancelledError):
      await asyncio.shield(_stop_process(process))
      raise
  if not result_file.is_file():
    raise RuntimeError(f"NX {stage} exited {code} without a result; see {log_file}")
  result = json.loads(result_file.read_text(encoding="utf-8"))
  if code != 0 or not result.get("ok"):
    raise RuntimeError(f"NX {stage}: {result.get('error', f'exit {code}')}; see {log_file}")
  logger.info("NX %s completed: %s", stage, result["output"])
  return result["output"]

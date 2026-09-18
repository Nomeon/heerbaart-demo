"""Machining Setup Instructions needs a real NX Manufacturing session."""
import asyncio
import json
import logging
import os
from pathlib import Path
import re
import tempfile

from nx_runner import PROJECT_DIR, _stop_process, custom_directory

logger = logging.getLogger(__name__)


def gui_environment(launcher: Path, profile: Path) -> dict[str, str]:
    # Use the same libraries as the working interactive Heerbaart launcher.
    # Read its SET assignments; never run or modify the batch file.
    env = {key.upper(): value for key, value in os.environ.items()
           if key.upper() not in {"OPENAI_API_KEY", "NX_CALLBACK_API_KEY", "NX_ENABLE_HEADLESS_GRAPHICS"}}
    for line in launcher.read_text().splitlines():
        match = re.match(r"set ([^=]+)=(.*)", line.strip(), re.I)
        if match:
            key, value = match.groups()
            env[key.upper()] = re.sub(r"%([^%]+)%", lambda m: env.get(m[1].upper(), m[0]), value)
    env["UGII_USER_PROFILE_DIR"] = str(profile)
    return env


async def run_setup_sheet(request: dict, work_root: Path) -> dict:
    install = Path(os.environ.get("NX_INSTALL_DIR", "C:/Program Files/Siemens/DesigncenterNX2512"))
    app = Path(os.environ.get("NX_MSI_APP_DIR", "C:/Heerbaart_Custom/NX CAM Machining Setup Instructions/app"))
    launcher = Path(os.environ.get("NX_GUI_LAUNCHER", "C:/Heerbaart_Custom/Heerbaart_NX2512.bat"))
    executable = install / "NXBIN" / "ugraf.exe"
    for required in (executable, launcher, app / "MachiningSetupInstructions.dll", app / "Backend.dll"):
        if not required.is_file():
            raise FileNotFoundError(required)
    work_root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="setup_sheet_", dir=work_root)).resolve()
    profile = Path(os.environ.get("NX_GUI_PROFILE_DIR", str(work_root.parent / "nx-gui-profile"))).resolve()
    profile.mkdir(parents=True, exist_ok=True)
    item = Path(request["item_dir"]).resolve()
    name = request["name"]
    output = item / f"{name}_INSTELBLAD.pdf"
    pending = work / output.name
    (work / "request.json").write_text(json.dumps(request, indent=2), encoding="utf-8")
    env = gui_environment(launcher, profile)
    env.update(HEERBAART_MSI_WORK=str(work), HEERBAART_MSI_APP=str(app.resolve()),
               HEERBAART_MSI_ITEM=str(item), HEERBAART_MSI_NAME=name,
               HEERBAART_MSI_CUSTOM=str(custom_directory()), HEERBAART_MSI_PDF=str(pending))
    logger.info("NX setup sheet starting; log: %s", work / "nx.log")
    with (work / "nx.log").open("wb") as log:
        process = await asyncio.create_subprocess_exec(
            str(executable), "-nx", "-auto=" + str(PROJECT_DIR / "nx" / "setup_sheet.vb"),
            cwd=work, env=env, stdout=log, stderr=asyncio.subprocess.STDOUT)
        try:
            code = await asyncio.wait_for(process.wait(), timeout=float(os.environ.get("NX_JOURNAL_TIMEOUT", "900")))
        except (TimeoutError, asyncio.CancelledError):
            await asyncio.shield(_stop_process(process))
            raise
    return publish_setup_sheet(work, output, code)


def publish_setup_sheet(work: Path, output: Path, code: int) -> dict:
    pending = work / output.name
    error = work / "error.txt"
    completed = (work / "success.txt").exists()
    # NX -auto can fail its own checks after the export journal has completed.
    # The journal's completion marker and a readable PDF remain required.
    auto_check_failed = code == 1 and "ATHENA_FAIL: Test failed with" in (work / "nx.log").read_text(errors="replace")
    if error.exists() or not completed or (code != 0 and not auto_check_failed):
        detail = error.read_text(encoding="utf-8-sig") if error.exists() else f"NX exited {code}; export completed={completed}"
        raise RuntimeError(f"Instelblad: {detail}; zie {work / 'nx.log'}")
    # Publish only a completed, readable PDF; a partial file never becomes a download.
    import fitz
    with fitz.open(pending) as document:
        if document.page_count == 0:
            raise RuntimeError("NX returned an empty setup sheet")
    if code:
        logger.warning("NX auto-check failed after completed PDF export; using validated PDF. Log: %s", work / "nx.log")
    pending.replace(output)
    result = {"setup_sheet": str(output)}
    (work / "result.json").write_text(json.dumps({"ok": True, "output": result}, indent=2), encoding="utf-8")
    logger.info("NX setup sheet completed: %s", output)
    return result

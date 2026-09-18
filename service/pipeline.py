"""One Elster family, one independent baseline, articles generated on demand."""

import argparse
import asyncio
import json
import logging
from pathlib import Path
import shutil

from nx_runner import run_nx
from drawing_analysis import analyze_drawing
from api.config import LoggingConfig, StorageConfig


SETUP_STAGES = ("load", "constraints", "holders", "position", "references")
PART_KINDS = ("PART", "ASSY", "CAD4CAM", "BLANK", "SETUP")
ACTIONS = ("extract", "baseline", "part", "structure", "setup", "ready", "article")
logger = logging.getLogger(__name__)


async def report(progress, stage, workflow, **details):
  if progress:
    await progress(stage, workflow, **details)


def article_row(family, article_number):
  row = next((item for item in family["articles"] if item["article_number"] == article_number), None)
  if row is None:
    raise ValueError(f"Article {article_number!r} is not in the extracted table")
  return row


def family_directory() -> Path:
  return StorageConfig().data_dir.resolve() / "elster-rev-d"


def _save_family(family: dict) -> None:
  destination = family_directory() / "family.json"
  temporary = destination.with_suffix(".tmp")
  temporary.write_text(json.dumps(family, indent=2), encoding="utf-8")
  temporary.replace(destination)


def _load_family() -> dict:
  return json.loads((family_directory() / "family.json").read_text(encoding="utf-8"))


async def read_family(pdf_path: Path) -> dict:
  root = family_directory()
  if (root / "family.json").exists() or any((root / "BASELINE").glob("*.prt")):
    raise FileExistsError("This family already exists; use the individual stages to continue it")
  table = await analyze_drawing(Path(pdf_path).resolve(), root)
  root.mkdir(parents=True, exist_ok=True)
  shutil.copyfile(pdf_path, root / "drawing.pdf")
  family = {
    "family": "elster-rev-d",
    **table.model_dump(),
    "baseline_source_article": table.articles[0].article_number,
    "baseline_ready": False,
    "setup_stage": None,
  }
  _save_family(family)
  logger.info("Extracted %s rows; BASELINE uses %s", len(table.articles), table.articles[0].article_number)
  return family


def _baseline_request(family: dict) -> dict:
  root = family_directory()
  item_dir = root / "BASELINE"
  return {
    "item_dir": str(item_dir), "name": "BASELINE",
    "pdf_path": str(root / "drawing.pdf"),
    "source_article": family["baseline_source_article"],
    "expressions": family["articles"][0]["expressions"],
  }


async def create_baseline_part(family: dict) -> dict:
  return await run_nx("part", _baseline_request(family), family_directory() / "work")


async def create_structure(family: dict) -> dict:
  return await run_nx("structure", _baseline_request(family), family_directory() / "work")


async def create_setup(family: dict, progress=None) -> dict:
  """Resume after the last completed setup stage, each in a fresh NX process."""
  completed = family.get("setup_stage")
  start = SETUP_STAGES.index(completed) + 1 if completed else 0
  result = {"setup": str(family_directory() / "BASELINE" / "BASELINE_SETUP.prt")}
  for stage in SETUP_STAGES[start:]:
    await report(progress, f"setup_{stage}", "baseline")
    result = await run_nx("setup", {
      **_baseline_request(family), "setup_stage": stage,
    }, family_directory() / "work")
    family = {**family, "setup_stage": stage, "baseline_ready": False}
    _save_family(family)
  return result


async def prepare_baseline(pdf_path: Path, article_number=None, progress=None) -> dict:
  await report(progress, "pdf_extract", "baseline")
  family = await read_family(pdf_path)
  if article_number:
    article_row(family, article_number)
  await report(progress, "baseline_part", "baseline")
  await create_baseline_part(family)
  await report(progress, "baseline_structure", "baseline")
  await create_structure(family)
  return await create_setup(family, progress)


def mark_baseline_ready(family: dict) -> dict:
  baseline = family_directory() / "BASELINE"
  if family.get("setup_stage") != "references":
    raise ValueError("Complete BASELINE setup construction before marking manual programming ready")
  for kind in PART_KINDS:
    if not (baseline / f"BASELINE_{kind}.prt").is_file():
      raise FileNotFoundError(baseline / f"BASELINE_{kind}.prt")
  _save_family({**family, "baseline_ready": True})
  return {"baseline_ready": True, "setup": str(baseline / "BASELINE_SETUP.prt")}


async def generate_article(family: dict, article_number: str, progress=None, material=None, amount=1,
                           resume_from="article_clone") -> dict:
  if resume_from not in {"article_clone", "geometry_update", "setup_refresh", "cam_regeneration", "postprocessing", "simulation", "measurement", "setup_sheet"}:
    raise ValueError(f"Unsupported article retry stage: {resume_from}")
  if not family["baseline_ready"]:
    raise ValueError("Save the manually programmed BASELINE and mark it ready first")
  row = article_row(family, article_number)
  if not article_number.isascii() or not article_number.isdigit():
    raise ValueError("Article numbers must be ASCII digits")
  root = family_directory()
  from nc_release import invalidate_release, released_nc
  item_dir = root / article_number
  if resume_from != "setup_sheet":
    invalidate_release(item_dir)
  (item_dir / f"{article_number}_INSTELBLAD.pdf").unlink(missing_ok=True)
  request = {
    "baseline_dir": str(root / "BASELINE"),
    "item_dir": str(root / article_number), "name": article_number,
    "expressions": row["expressions"],
    "material": material, "amount": amount,
  }
  outputs = {kind.lower(): str(root / article_number / f"{article_number}_{kind}.prt")
             for kind in PART_KINDS}
  if resume_from == "setup_sheet":
    if released_nc(item_dir, article_number) is None:
      raise ValueError("Simuleer het NC-programma voordat je het instelblad maakt.")
    from nx.simulation import machine_time_seconds
    simulation = json.loads((item_dir / "simulation.json").read_text(encoding="utf-8"))
    outputs["simulation_time_seconds"] = machine_time_seconds(simulation["machine_time"])
    return await export_setup_sheet(request, outputs, root, progress)
  if resume_from == "article_clone":
    await report(progress, "article_clone", "article")
    outputs = await run_nx("clone", request, root / "work")
  else:
    # Resume the repaired article in place; never copy over it from BASELINE.
    for filename in outputs.values():
      if not Path(filename).is_file():
        raise FileNotFoundError(f"Cannot resume article; required part is missing: {filename}")
  if resume_from in {"article_clone", "geometry_update"}:
    await report(progress, "geometry_update", "article")
    await run_nx("update", request, root / "work")
  if resume_from in {"article_clone", "geometry_update", "measurement"}:
    await report(progress, "measurement", "article")
    outputs.update(await run_nx("measurement", request, root / "work"))
    await report(progress, "measurement", "article", weights=outputs["weights"])
  if resume_from in {"article_clone", "geometry_update", "measurement", "setup_refresh"}:
    await report(progress, "setup_refresh", "article")
    outputs.update(await run_nx("refresh", request, root / "work"))
  if resume_from not in {"postprocessing", "simulation"}:
    await report(progress, "cam_regeneration", "article")
    outputs.update(await run_nx("cam", request, root / "work"))
  if resume_from != "simulation":
    await report(progress, "postprocessing", "article")
    outputs.update(await run_nx("post", request, root / "work"))
  await report(progress, "simulation", "article")
  outputs.update(await run_nx("simulation", request, root / "work"))
  return await export_setup_sheet(request, outputs, root, progress)


async def export_setup_sheet(request, outputs, root, progress):
  await report(progress, "setup_sheet", "article",
               simulation_time_seconds=outputs["simulation_time_seconds"])
  outputs.update(await run_nx("setup_sheet", request, root / "work"))
  return outputs


async def prepare_quotation(drawing_path, article_number, progress=None, material=None, amount=1):
  root = family_directory()
  if not (root / "family.json").exists():
    await prepare_baseline(Path(drawing_path), article_number, progress)
  family = _load_family()
  article_row(family, article_number)
  if family.get("setup_stage") != "references" or not all(
    (root / "BASELINE" / f"BASELINE_{kind}.prt").is_file() for kind in PART_KINDS
  ):
    raise ValueError("BASELINE is incomplete. Continue its local stages before requesting an article.")
  if family["baseline_ready"]:
    result = await generate_article(family, article_number, progress, material, amount)
    return {**result, "outcome": "ARTICLE_CREATED", "workflow": "article"}
  return {"outcome": "AWAITING_PROGRAMMING", "workflow": "baseline",
          "setup": str(root / "BASELINE" / "BASELINE_SETUP.prt")}


async def run_job(action: str, *, drawing_path=None, article_number=None, job_id=None,
                  material=None, amount=1, progress=None, resume_from=None) -> dict:
  logger.info("Job %s: %s %s", job_id or "local", action, article_number or "BASELINE")
  if action == "prepare_quotation":
    return await prepare_quotation(drawing_path, article_number, progress, material, amount)
  if action == "retry_article":
    result = await generate_article(_load_family(), article_number, progress, material, amount, resume_from)
    return {**result, "outcome": "ARTICLE_CREATED", "workflow": "article"}
  if action == "approve_baseline_and_generate":
    family = _load_family()
    article_row(family, article_number)
    mark_baseline_ready(family)
    result = await generate_article(_load_family(), article_number, progress, material, amount)
    return {**result, "outcome": "ARTICLE_CREATED", "workflow": "article"}
  if action in {"extract", "baseline"}:
    if drawing_path is None:
      raise ValueError(f"drawing is required for {action}")
    if action == "extract":
      return await read_family(Path(drawing_path))
    return await prepare_baseline(Path(drawing_path), progress=progress)
  family = _load_family()
  if action == "part":
    return await create_baseline_part(family)
  if action == "structure":
    return await create_structure(family)
  if action == "setup":
    return await create_setup(family)
  if action == "ready":
    return mark_baseline_ready(family)
  if action == "article":
    return await generate_article(family, article_number, progress, material, amount)
  raise ValueError(f"Unknown action: {action}")


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("action", choices=ACTIONS)
  parser.add_argument("--drawing", type=Path)
  parser.add_argument("--article", dest="article_number")
  parser.add_argument("--material")
  args = parser.parse_args()
  logging.basicConfig(level=LoggingConfig().level, format=LoggingConfig().format)
  result = asyncio.run(run_job(args.action, drawing_path=args.drawing,
                              article_number=args.article_number, material=args.material))
  print(json.dumps(result, indent=2))


if __name__ == "__main__":
  main()

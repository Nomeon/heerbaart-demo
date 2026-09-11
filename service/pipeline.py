"""One Elster family, one independent baseline, articles generated on demand."""

import argparse
import asyncio
import json
import logging
from pathlib import Path
import shutil

from nx_runner import run_nx
from pdf_table import extract_table
from api.config import LoggingConfig, StorageConfig


SETUP_STAGES = ("load", "constraints", "holders", "position", "references")
PART_KINDS = ("PART", "ASSY", "CAD4CAM", "BLANK", "SETUP")
ACTIONS = ("extract", "baseline", "part", "structure", "setup", "ready", "article")
logger = logging.getLogger(__name__)


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
  table = await extract_table(Path(pdf_path).resolve())
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


async def create_setup(family: dict) -> dict:
  """Resume after the last completed setup stage, each in a fresh NX process."""
  completed = family.get("setup_stage")
  start = SETUP_STAGES.index(completed) + 1 if completed else 0
  result = {"setup": str(family_directory() / "BASELINE" / "BASELINE_SETUP.prt")}
  for stage in SETUP_STAGES[start:]:
    result = await run_nx("setup", {
      **_baseline_request(family), "setup_stage": stage,
    }, family_directory() / "work")
    family = {**family, "setup_stage": stage, "baseline_ready": False}
    _save_family(family)
  return result


async def prepare_baseline(pdf_path: Path) -> dict:
  family = await read_family(pdf_path)
  await create_baseline_part(family)
  await create_structure(family)
  return await create_setup(family)


def mark_baseline_ready(family: dict) -> dict:
  baseline = family_directory() / "BASELINE"
  if family.get("setup_stage") != "references":
    raise ValueError("Complete BASELINE setup construction before marking manual programming ready")
  for kind in PART_KINDS:
    if not (baseline / f"BASELINE_{kind}.prt").is_file():
      raise FileNotFoundError(baseline / f"BASELINE_{kind}.prt")
  _save_family({**family, "baseline_ready": True})
  return {"baseline_ready": True, "setup": str(baseline / "BASELINE_SETUP.prt")}


async def generate_article(family: dict, article_number: str) -> dict:
  if not family["baseline_ready"]:
    raise ValueError("Save the manually programmed BASELINE and mark it ready first")
  row = next((item for item in family["articles"] if item["article_number"] == article_number), None)
  if row is None:
    raise ValueError(f"Article {article_number!r} is not in the extracted table")
  if not article_number.isascii() or not article_number.isdigit():
    raise ValueError("Article numbers must be ASCII digits")
  root = family_directory()
  request = {
    "baseline_dir": str(root / "BASELINE"),
    "item_dir": str(root / article_number), "name": article_number,
    "expressions": row["expressions"],
  }
  outputs = await run_nx("clone", request, root / "work")
  await run_nx("update", request, root / "work")
  refreshed = await run_nx("refresh", request, root / "work")
  return {**outputs, **refreshed}


async def run_job(action: str, *, drawing_path=None, article_number=None, job_id=None) -> dict:
  logger.info("Job %s: %s %s", job_id or "local", action, article_number or "BASELINE")
  if action in {"extract", "baseline"}:
    if drawing_path is None:
      raise ValueError(f"drawing is required for {action}")
    if action == "extract":
      return await read_family(Path(drawing_path))
    return await prepare_baseline(Path(drawing_path))
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
    return await generate_article(family, article_number)
  raise ValueError(f"Unknown action: {action}")


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("action", choices=ACTIONS)
  parser.add_argument("--drawing", type=Path)
  parser.add_argument("--article", dest="article_number")
  args = parser.parse_args()
  logging.basicConfig(level=LoggingConfig().level, format=LoggingConfig().format)
  result = asyncio.run(run_job(args.action, drawing_path=args.drawing, article_number=args.article_number))
  print(json.dumps(result, indent=2))


if __name__ == "__main__":
  main()

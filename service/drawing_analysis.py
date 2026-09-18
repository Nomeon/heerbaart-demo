"""One cached Elster table, independent of NX family/baseline creation."""

import asyncio
import hashlib
import json
from pathlib import Path

from pdf_table import FamilyTable, extract_table

_analysis_lock = asyncio.Lock()


async def analyze_drawing(pdf_path: Path, family_root: Path) -> FamilyTable:
  digest = await asyncio.to_thread(lambda: hashlib.sha256(pdf_path.read_bytes()).hexdigest())
  cache = family_root.parent / "elster-analysis.json"
  async with _analysis_lock:
    # An existing POC family is the source of truth for its drawing and dimensions.
    family_file = family_root / "family.json"
    family_pdf = family_root / "drawing.pdf"
    if family_file.exists():
      if not family_pdf.is_file() or hashlib.sha256(family_pdf.read_bytes()).hexdigest() != digest:
        raise ValueError("Use the same Elster Rev.D PDF as the existing NX family")
      return FamilyTable.model_validate(json.loads(family_file.read_text(encoding="utf-8")))
    if cache.exists():
      saved = json.loads(cache.read_text(encoding="utf-8"))
      if saved.get("sha256") == digest:
        return FamilyTable.model_validate(saved)
    table = await extract_table(pdf_path)
    cache.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache.with_suffix(".tmp")
    temporary.write_text(json.dumps({"sha256": digest, **table.model_dump()}), encoding="utf-8")
    temporary.replace(cache)
    return table

"""Validate the explicit NX request, without extracting or inventing article rows."""

import math
from pathlib import Path


def validate_request(request):
    if not isinstance(request, dict) or request.get("name") != "BASELINE":
        raise ValueError("build_part requires name='BASELINE'; article generation uses native cloning")
    paths = {}
    for key in ("item_dir", "pdf_path", "custom_dir", "work_dir"):
        raw = request.get(key)
        if not isinstance(raw, str) or not raw or "\x00" in raw or not Path(raw).is_absolute():
            raise ValueError(f"{key} must be an absolute path")
        paths = {**paths, key: Path(raw).resolve()}
    if not paths["pdf_path"].is_file() or paths["pdf_path"].suffix.lower() != ".pdf":
        raise ValueError("pdf_path must identify the supplied source PDF")
    if not paths["custom_dir"].is_dir():
        raise ValueError("custom_dir must identify the installed Heerbaart NX custom directory")
    for key in ("item_dir", "work_dir"):
        if paths[key].exists() and not paths[key].is_dir():
            raise ValueError(f"{key} is not a directory")
    names = ("DT", "FA", "DR", "FR", "FB", "DS", "DL")
    supplied = request.get("expressions")
    if not isinstance(supplied, dict) or set(supplied) != set(names):
        raise ValueError("expressions must contain exactly DT, FA, DR, FR, FB, DS, DL")
    if any(
        isinstance(supplied[key], bool) or not isinstance(supplied[key], (int, float))
        or not math.isfinite(supplied[key]) or supplied[key] <= 0
        for key in names
    ):
        raise ValueError("The seven public expressions must be finite positive numbers, not formulas")
    values = {key: float(supplied[key]) for key in names}
    if values["DT"] <= 180:
        raise ValueError("DT <= 180 is unsupported: the source STAP1 inlet segments collapse; NX laptop review required")
    inlet_length = (values["DT"] - 180) / (2 * 0.1227845609)
    body_length = 600 - 2 * values["FR"] - 2 * values["FB"] - (values["DR"] - 250)
    if (
        inlet_length >= 300 or values["DT"] >= 269.9 or body_length <= 0
        or values["DR"] <= 250 or values["FA"] <= max(269.9, values["DR"])
    ):
        raise ValueError("The supplied row does not fit the fixed Rev.D revolve topology")
    if min(
        (values["FA"] - values["DL"] - values["DS"]) / 2 - 0.2,
        (values["DL"] - values["DS"] - values["DR"]) / 2 - 0.2,
    ) <= 0:
        raise ValueError("The supplied DS/DL flange holes have no positive inner or outer ligament")
    source_article = request.get("source_article", "")
    if not isinstance(source_article, str) or "\x00" in source_article or len(source_article) > 80:
        raise ValueError("source_article must be a short source-row identifier")
    return paths, values, source_article

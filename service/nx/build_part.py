"""NX entry: build_part(request) -> {'part': absolute BASELINE_PART.prt path}."""

import hashlib
import math
from pathlib import Path
import tempfile


def build_part(request: dict) -> dict:
    """Build the fixed ElsterRevD family from the supplied first PDF table row.

    Required: absolute item_dir, pdf_path, custom_dir, work_dir; name='BASELINE';
    expressions={DT, FA, DR, FR, FB, DS, DL} with finite positive numbers.
    Optional source_article records provenance, never the identity of BASELINE.
    Called only by the parent journal inside NX Python, not regular Python.
    """
    from .model.request import validate_request
    from .model.hb_catalog import load_threads

    paths, values, source_article = validate_request(request)
    name = request["name"]
    output = paths["item_dir"] / (name + "_PART.prt")
    if output.exists():
        raise FileExistsError(f"Refusing to replace an existing BASELINE part: {output}")
    threads = load_threads(paths["custom_dir"])
    with paths["pdf_path"].open("rb") as stream:
        pdf_hash = hashlib.file_digest(stream, "sha256").hexdigest()

    import NXOpen
    from .model import builders, common

    paths["item_dir"].mkdir(parents=True, exist_ok=True)
    paths["work_dir"].mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix=name + "_model_", dir=paths["work_dir"]))
    session = NXOpen.Session.GetSession()
    step = "STAP1_REVOLVE_OUTLINE"
    try:
        part = builders.step1.create_part(session, str(scratch / (name + "_PART.prt")))
        common.set_attributes(part, {
            "ELSTER_PART_NUMBER": name,
            "ELSTER_FAMILY": "ElsterRevD",
            "ELSTER_DRAWING_REVISION": "D",
            "ELSTER_SCOPE": "ELSTER_REV_D_STAP1_11",
            "ELSTER_ITEM_ROLE": "NON_SALEABLE_BASELINE",
            "ELSTER_SOURCE_ARTICLE": source_article,
            "ELSTER_SOURCE_PDF": str(paths["pdf_path"]),
            "ELSTER_SOURCE_PDF_SHA256": pdf_hash,
            "ELSTER_INPUT_POLICY": "SUPPLIED_PDF_ROW_FIXED_REVIEWED_REV_D_GEOMETRY",
        })
        common.create_expressions(
            part, [(key, repr(value), "mm") for key, value in values.items()],
            "Supplied first PDF table row; independent non-saleable BASELINE",
        )
        for index, (step, create, expressions) in enumerate(builders.STAGES):
            print("Building Elster " + step, flush=True)
            if index:
                # The original journals reopen a saved native part at every STAP boundary.
                part = common.reopen(session, part)
            common.create_expressions(part, expressions)
            create(part, threads)
            common.update(step)
            common.solid_body(part)
            part.SetAttribute("ELSTER_WORKFLOW_STEP", step)
        for key, expected in values.items():
            actual = float(part.Expressions.FindObject(key).Value)
            if not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-8):
                raise RuntimeError(f"Public expression {key} is {actual}, expected {expected}")
        builders.step11.set_product_display(session, part)
        common.save(part)
        if output.exists():
            raise FileExistsError(f"BASELINE destination now exists: {output}")
        part.SaveAs(str(output)).Dispose()
        if not output.is_file():
            raise RuntimeError(f"NX did not save the requested final part: {output}")
        return {"part": str(output)}
    except Exception as exc:
        raise RuntimeError(f"Elster {step} failed; scratch: {scratch}: {exc}") from exc

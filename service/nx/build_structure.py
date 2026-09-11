"""Build the associative structure in an NX process, without rebuilding PART."""

from .assembly import blank_component, cad4cam, parent
from .assembly.orientation import collect_orientation_diagnostics
from .assembly.paths import request_paths


def build_structure(request: dict) -> dict:
    import NXOpen
    import NXOpen.UF

    paths = request_paths(request)
    part_file = paths.part("PART")
    if not part_file.is_file():
        raise FileNotFoundError(part_file)
    for kind in ("ASSY", "CAD4CAM", "BLANK"):
        if paths.part(kind).exists():
            raise FileExistsError(f"Initial construction will not overwrite {paths.part(kind)}")
    session = NXOpen.Session.GetSession()
    _part, status = session.Parts.OpenBaseDisplay(str(part_file))
    status.Dispose()
    orientation = collect_orientation_diagnostics(NXOpen, session.Parts.Work, 0.01, "ZC")
    # PART stays untouched. Alignment and its color are occurrence overrides in ASSY.
    context = {
        "currentFile": str(part_file),
        "name": paths.name,
        "outputDir": str(paths.item_dir),
        "stepDir": str(paths.work_dir),
        "state": {"orientation": orientation},
    }
    assembly = parent.run(context)
    context = {**context, "currentFile": assembly["outputFile"]}
    cad = cad4cam.run(context)
    context = {**context, "state": {**context["state"], **cad["state"]}}
    blank = blank_component.run(context)
    return {
        "assy": str(paths.part("ASSY")),
        "cad4cam": cad["cad4camFile"],
        "blank": blank["blankFile"],
    }

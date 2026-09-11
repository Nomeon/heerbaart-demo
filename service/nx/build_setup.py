"""NX-only setup entry points. Every initial stage needs a separate NX process."""

from .assembly.paths import request_paths


SETUP_STAGES = ("load", "constraints", "holders", "position", "references")


def build_setup(request: dict) -> dict:
    import NXOpen

    from .setup import common, constraints, load, stages

    paths = request_paths(request)
    stage = request.get("setup_stage")
    if stage not in SETUP_STAGES:
        raise ValueError(f"setup_stage must be one of {SETUP_STAGES}")
    if stage == "load" and paths.part("SETUP").exists():
        raise FileExistsError("Initial setup loading will not overwrite an existing SETUP")
    if stage != "load" and not paths.part("SETUP").is_file():
        raise FileNotFoundError(paths.part("SETUP"))
    if not paths.device_root.is_dir():
        raise FileNotFoundError(paths.device_root)
    session = NXOpen.Session.GetSession()
    session.SetUndoMark(NXOpen.Session.MarkVisibility.Visible, f"Setup {stage}")
    common.load_product_parts(session, paths)
    if stage == "load":
        load.run(paths)
    elif stage == "constraints":
        constraints.run(paths)
    elif stage == "holders":
        stages.attach_holders(paths)
    else:
        stages.position_and_reference(paths, references=stage == "references")
    return {"setup": str(paths.part("SETUP")), "setup_stage": stage}


def refresh_setup(request: dict) -> dict:
    """Refresh a native-cloned SETUP after its item-local dependencies are saved."""
    from .setup.refresh import run

    return run(request_paths(request))

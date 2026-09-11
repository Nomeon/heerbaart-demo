"""Native article cloning and CAD updates, each in its own fresh NX process.

The dispatcher must call clone_article, then update_article, then refresh_setup
in three separate processes. SETUP is cloned on disk, never opened here.
UF signatures/enums: NX 2312 Python reference a66718, a66722, a66742, a66750.
https://docs.sw.siemens.com/documentation/external/PL20230425446868577/en-US/custom_api/nxopen_python_ref/a66718.html
"""

import math
import logging
from pathlib import Path
import re
import sys


_SUFFIXES = ("PART", "ASSY", "CAD4CAM", "BLANK", "SETUP")
_SAVE_ORDER = ("part", "cad4cam", "blank", "assy")
_EXPRESSIONS = ("DT", "FA", "DR", "FR", "FB", "DS", "DL")


def _values(request):
    if not isinstance(request, dict):
        raise TypeError("Article request must be a dictionary")
    supplied = request.get("expressions")
    if not isinstance(supplied, dict) or set(supplied) != set(_EXPRESSIONS):
        raise ValueError("expressions must contain exactly DT, FA, DR, FR, FB, DS, DL")
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        for value in supplied.values()
    ):
        raise ValueError("Article expressions must be numeric millimeters, not formulas")
    try:
        values = {key: float(supplied[key]) for key in _EXPRESSIONS}
    except OverflowError as exc:
        raise ValueError("Article expressions must be finite millimeter values") from exc
    if not all(math.isfinite(value) for value in values.values()):
        raise ValueError("Article expressions must be finite millimeter values")
    if values["DT"] <= 180:
        raise ValueError(
            f"DT={values['DT']:g} mm is unsupported: DT must be greater than 180 mm. "
            "The retained baseline STAP1 inlet topology collapses or reverses at "
            "DT <= 180 mm; support is pending NX laptop review."
        )
    if any(value <= 0 for value in values.values()):
        raise ValueError("Article expressions must be positive millimeter values")
    return values


def _files(request):
    name = request.get("name")
    if not isinstance(name, str) or not re.fullmatch(r"[0-9]{1,80}", name):
        raise ValueError("name must be an article digit string (1-80 ASCII digits)")
    paths = {}
    for key in ("baseline_dir", "item_dir", "work_dir", "custom_dir"):
        raw = request.get(key)
        if not isinstance(raw, str) or not raw or "\x00" in raw or not Path(raw).is_absolute():
            raise ValueError(f"{key} must be an absolute directory path")
        path = Path(raw).resolve()
        if path.exists() and not path.is_dir():
            raise NotADirectoryError(path)
        paths = {**paths, key: path}
    if paths["item_dir"].name != name:
        raise ValueError("item_dir must be the numeric article folder matching name")
    for key in ("baseline_dir", "custom_dir"):
        if not paths[key].is_dir():
            raise FileNotFoundError(f"{key} does not exist: {paths[key]}")
    for key in ("item_dir", "work_dir"):
        if any(paths[key].is_relative_to(paths[root]) for root in ("baseline_dir", "custom_dir")):
            raise ValueError(f"{key} must be outside the baseline and shared NX library")
    if paths["work_dir"] == paths["item_dir"]:
        raise ValueError("work_dir must be separate from item_dir")
    sources = {
        suffix.lower(): paths["baseline_dir"] / f"BASELINE_{suffix}.prt"
        for suffix in _SUFFIXES
    }
    targets = {
        suffix.lower(): paths["item_dir"] / f"{name}_{suffix}.prt"
        for suffix in _SUFFIXES
    }
    _require_files(sources)
    return sources, targets


def _require_files(files):
    for path in files.values():
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Required native part must be a regular, non-symlink file: {path}")


def _require_absent(files):
    for path in files.values():
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"Native cloning will not overwrite an existing destination: {path}")


def _fresh_session():
    import NXOpen

    session = NXOpen.Session.GetSession()
    if tuple(session.Parts):
        raise RuntimeError("Article stages require a fresh NX process before any parts are loaded")
    # These are process-local settings; never save load options into the library.
    options = session.Parts.LoadOptions
    options.PartLoadOption = NXOpen.LoadOptions.LoadOption.FullyLoad
    options.ComponentsToLoad = NXOpen.LoadOptions.LoadComponents.All
    options.ComponentLoadMethod = NXOpen.LoadOptions.LoadMethod.AsSaved
    options.AllowSubstitution = False
    options.AbortOnFailure = True
    options.GenerateMissingPartFamilyMembers = False
    options.SetInterpartData(True, NXOpen.LoadOptions.Parent.All)
    return session


def _uf_status(code, operation):
    # UF Clone methods without output arguments document an integer return code.
    if code != 0:
        raise RuntimeError(f"Native UF clone {operation} returned {code!r}; refusing to continue")


def _configure_clone(clone, sources, targets):
    from NXOpen.UF import Clone

    _uf_status(clone.SetDefAction(Clone.Action.UF_CLONE_retain), "SetDefAction(retain)")
    _uf_status(clone.SetDefAssocFileCopy(False), "SetDefAssocFileCopy(False)")
    _uf_status(clone.SetDryrun(False), "SetDryrun(False)")
    status = clone.AddAssembly(str(sources["setup"]))
    # UF.Part.LoadStatus is a data structure, not NXOpen.PartLoadStatus/Dispose.
    if status.Failed or status.UserAbort or status.NParts:
        raise RuntimeError(
            "Native clone could not resolve the complete baseline SETUP: "
            f"failed={status.Failed}, aborted={status.UserAbort}, "
            f"files={status.FileNames!r}, statuses={status.Statuses!r}"
        )
    _uf_status(clone.StartIteration(), "StartIteration")
    present = frozenset()
    while True:
        source = clone.Iterate()
        if not source:
            break
        present = present | {Path(source).resolve()}
    # Iterate terminates at end; AddPart is forbidden while iteration is active.
    for key, source in sources.items():
        if source not in present:
            _uf_status(clone.AddPart(str(source)), f"AddPart({source})")
        _uf_status(
            clone.SetAction(str(source), Clone.Action.UF_CLONE_clone, None),
            f"SetAction(clone, {source})",
        )
        _uf_status(
            clone.SetNaming(str(source), Clone.NamingTechnique.UF_CLONE_user_name, str(targets[key])),
            f"SetNaming({source}, {targets[key]})",
        )


def clone_article(request: dict) -> dict:
    """Clone five BASELINE parts on disk, retaining every other referenced part.

    Returns part/assy/cad4cam/blank/setup absolute paths. There is no filesystem
    copy, SaveAs, overwrite action, or fallback. Failures may leave partial native
    outputs; the dispatcher must stop rather than update or retry over them.
    """
    _values(request)  # Reject unsupported topology before touching UF or destinations.
    sources, targets = _files(request)
    _require_absent(targets)
    _fresh_session()

    import NXOpen.UF

    clone = NXOpen.UF.UFSession.GetUFSession().Clone
    _uf_status(clone.Terminate(), "Terminate before initialise")
    try:
        _uf_status(
            clone.Initialise(NXOpen.UF.Clone.OperationClass.UF_CLONE_clone_operation),
            "Initialise(clone)",
        )
        targets["part"].parent.mkdir(parents=True, exist_ok=True)
        _configure_clone(clone, sources, targets)
        _require_absent(targets)
        failures = clone.InitNamingFailures()
        failures = clone.PerformClone(failures)
        if failures.NFailures:
            raise RuntimeError(
                f"Native clone reported {failures.NFailures} naming failures: "
                f"inputs={failures.InputNames!r}, outputs={failures.OutputNames!r}, "
                f"statuses={failures.Statuses!r}"
            )
    finally:
        original_error = sys.exception()
        try:
            _uf_status(clone.Terminate(), "Terminate")
        except Exception:
            if original_error is None:
                raise
            logging.exception("UF clone cleanup failed while handling %s", original_error)
    _require_files(targets)
    return {key: str(path) for key, path in targets.items()}


def _load_status(status, operation):
    try:
        if status.NumberUnloadedParts:
            details = "; ".join(
                f"{status.GetPartName(index)}: {status.GetStatusDescription(index)}"
                for index in range(status.NumberUnloadedParts)
            )
            raise RuntimeError(f"{operation}: {details}")
    finally:
        status.Dispose()


def _article_parts(session, targets):
    expected = {targets[key] for key in _SAVE_ORDER}
    loaded = {Path(part.FullPath).resolve(): part for part in session.Parts}
    if set(loaded) != expected:
        missing = sorted(str(path) for path in expected - set(loaded))
        unexpected = sorted(str(path) for path in set(loaded) - expected)
        raise RuntimeError(
            "CAD update requires only the four article-owned PART/CAD4CAM/BLANK/ASSY "
            f"parts, never SETUP or baseline/library parts; missing={missing}, unexpected={unexpected}"
        )
    return {key: loaded[targets[key]] for key in _SAVE_ORDER}


def _update(session, mark):
    manager = session.UpdateManager
    for label, operation in (
        ("model", manager.DoUpdate),
        ("WAVE/interpart", manager.DoInterpartUpdate),
        ("assembly constraints", manager.DoAssemblyConstraintsUpdate),
        ("final model", manager.DoUpdate),
    ):
        count = operation(mark)
        # DoInterpartUpdate and DoAssemblyConstraintsUpdate return void, not counts.
        if count or manager.ErrorList.Length:
            raise RuntimeError(f"Article {label} update failed: {count or manager.ErrorList.Length} NX errors")


def _edit_parameters(part, values):
    import NXOpen

    if part.PartUnits != NXOpen.BasePart.Units.Millimeters:
        raise ValueError("The cloned PART must use millimeters")
    mm = part.UnitCollection.FindObject("MilliMeter")
    expressions = {key: part.Expressions.FindObject(key) for key in _EXPRESSIONS}
    for key, expression in expressions.items():
        if (
            expression.OwningPart.Tag != part.Tag or expression.Type != "Number"
            or expression.Units is None or expression.Units.Tag != mm.Tag
            or expression.IsInterpartExpression or expression.IsNoUpdate
        ):
            raise ValueError(f"{key} must be a local, updatable millimeter number expression in the cloned PART")
    for key, expression in expressions.items():
        expression.SetFormula(repr(values[key]))


def _save_part(part):
    import NXOpen

    status = part.Save(
        NXOpen.BasePart.SaveComponents.FalseValue,
        NXOpen.BasePart.CloseAfterSave.FalseValue,
    )
    try:
        if status.NumberUnsavedParts or status.NumberUnsavedObjects:
            codes = [status.GetStatus(index) for index in range(status.NumberUnsavedParts)]
            raise RuntimeError(
                f"NX failed to save article part {part.FullPath}: "
                f"statuses={codes}, unsaved objects={status.NumberUnsavedObjects}"
            )
    finally:
        status.Dispose()


def update_article(request: dict) -> dict:
    """Update a completed disk clone; return only the four individually saved paths.

    SETUP remains unopened and unchanged until the dispatcher's fresh third-stage
    refresh_setup call. Baseline PDF/source-row provenance stays inherited.
    """
    values = _values(request)
    sources, targets = _files(request)
    _require_files(targets)
    for target in targets.values():
        if any(target.samefile(source) for source in sources.values()):
            raise ValueError(f"Article destination aliases a baseline original: {target}")
    session = _fresh_session()
    assembly, status = session.Parts.OpenBaseDisplay(str(targets["assy"]))
    _load_status(status, "Open article ASSY with full dependencies")
    _load_status(session.Parts.EnsurePartsLoadedFully([assembly], True), "Fully load article dependencies")
    parts = _article_parts(session, targets)

    import NXOpen

    session.Parts.SetWork(parts["part"])
    mark = session.SetUndoMark(NXOpen.Session.MarkVisibility.Invisible, "Update cloned article")
    session.UpdateManager.SetDefaultUpdateFailureAction(NXOpen.Update.FailureOption.Undo)
    _edit_parameters(parts["part"], values)
    for key, part in parts.items():
        for title, value in {
            "ELSTER_PART_NUMBER": request["name"],
            "ELSTER_ITEM_ROLE": "ARTICLE",
            "source.baseline": str(sources[key]),
        }.items():
            part.SetUserAttribute(title, -1, value, NXOpen.Update.Option.Later)
    _update(session, mark)
    _article_parts(session, targets)
    body = next((body for body in parts["part"].Bodies if body.IsSolidBody), None)
    if body is None:
        raise RuntimeError("Updated article PART has no solid body")
    for key, expected in values.items():
        actual = float(parts["part"].Expressions.FindObject(key).Value)
        if not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-8):
            raise RuntimeError(f"Updated {key} is {actual:g} mm, expected {expected:g} mm")
    session.Parts.SetWork(parts["assy"])
    for key in _SAVE_ORDER:
        _save_part(parts[key])
    return {key: str(targets[key]) for key in _SAVE_ORDER}

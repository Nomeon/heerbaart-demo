"""Post O1234 using Bob's recorded Okuma settings, with article-owned output."""

import shutil


def post_article(request):
    import NXOpen
    import NXOpen.CAM
    from .assembly.paths import request_paths
    from .cam import _article_program, _program_operations, _check_toolpaths
    from .setup import common
    from .variant import _save_part
    from nc_release import invalidate_release

    paths = request_paths(request)
    invalidate_release(paths.item_dir)
    session = NXOpen.Session.GetSession()
    common.load_product_parts(session, paths)
    part = common.open_display(session, paths.part("SETUP"), paths.custom_dir)
    if not session.IsCamSessionInitialized():
        session.CreateCamSession()
    program = _article_program(part)
    status = NXOpen.CAM.CAMObject.Status
    _check_toolpaths(_program_operations(program), {status.Complete, status.Repost, status.Approved})

    # Post into this run's fresh directory so an older .min cannot count as success.
    output = paths.work_dir / f"{paths.name}-SETUP.min"
    setup = part.CAMSetup
    setup.DeleteMachineCode()
    setup.OutputBallCenter = False
    print(f"POST: {paths.name} / {program.Name} -> {output}", flush=True)
    setup.PostprocessWithPostModeSetting(
        [program], "Okuma_MultusU4000_1SW", str(output),
        NXOpen.CAM.CAMSetup.OutputUnits.PostDefined,
        NXOpen.CAM.CAMSetup.PostprocessSettingsOutputWarning.PostDefined,
        NXOpen.CAM.CAMSetup.PostprocessSettingsReviewTool.PostDefined,
        NXOpen.CAM.CAMSetup.PostprocessSettingsPostMode.Normal,
    )
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"Postprocessor heeft geen NC-programma gemaakt: {output}")
    _save_part(part)
    common.close_setup(part)
    destination = paths.item_dir / output.name
    shutil.copy2(output, destination)
    print(f"POST: saved {destination} ({destination.stat().st_size} bytes)", flush=True)
    return {"setup": str(paths.part("SETUP")), "nc_program": str(destination)}

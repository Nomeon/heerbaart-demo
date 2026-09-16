"""Regenerate article program O1234; no posting, simulation, or time import."""


def _article_program(part):
    import NXOpen.CAM

    root = part.CAMSetup.GetRoot(NXOpen.CAM.CAMSetupView.ProgramOrder)

    def find(group):
        if group.Name == "O1234":
            return group
        for member in group.GetMembers():
            if isinstance(member, NXOpen.CAM.NCGroup):
                found = find(member)
                if found is not None:
                    return found
        return None

    program = find(root)
    if program is None:
        raise RuntimeError("CAM-programma O1234 ontbreekt in de artikelsetup.")
    return program


def _program_operations(group):
    import NXOpen.CAM

    operations = []
    for member in group.GetMembers():
        if isinstance(member, NXOpen.CAM.Operation):
            operations.append(member)
        elif isinstance(member, NXOpen.CAM.NCGroup):
            operations.extend(_program_operations(member))
    return operations


def _check_toolpaths(operations, valid_statuses):
    if not operations:
        raise RuntimeError("Het NX-programma bevat geen CAM-bewerkingen om te regenereren.")
    failures = []
    for operation in operations:
        status = operation.GetStatus()
        has_path = operation.AskPathExists()
        print(f"CAM {operation.Name}: status={status}, toolpath={has_path}", flush=True)
        if status not in valid_statuses or not has_path:
            failures.append(f"{operation.Name} (status={status}, toolpath={has_path})")
    if failures:
        raise RuntimeError("Gereedschapsbanen niet volledig gegenereerd: " + "; ".join(failures))


def regenerate_toolpaths(request):
    import NXOpen
    import NXOpen.CAM
    from .assembly.paths import request_paths
    from .setup import common
    from .variant import _save_part

    paths = request_paths(request)
    session = NXOpen.Session.GetSession()
    common.load_product_parts(session, paths)
    part = common.open_display(session, paths.part("SETUP"), paths.custom_dir)
    if not session.IsCamSessionInitialized():
        session.CreateCamSession()
    program = _article_program(part)
    operations = _program_operations(program)
    if not operations:
        raise RuntimeError("Het NX-programma bevat geen CAM-bewerkingen om te regenereren.")
    print(f"CAM: regenerating {program.Name}: {len(operations)} operations in the existing program order", flush=True)
    # Generate the program group so NX retains its operation order/dependencies.
    part.CAMSetup.GenerateToolPath([program])
    status = NXOpen.CAM.CAMObject.Status
    valid = {status.Complete, status.Repost, status.Approved}
    # Repost means the toolpath is current but its NC needs posting (a later step).
    _check_toolpaths(operations, valid)
    _save_part(part)
    common.close_setup(part)
    part = common.open_display(session, paths.part("SETUP"), paths.custom_dir)
    program = _article_program(part)
    saved_operations = _program_operations(program)
    _check_toolpaths(saved_operations, valid)
    common.close_setup(part)
    return {"setup": str(paths.part("SETUP")), "toolpaths_generated": True,
            "operation_count": len(saved_operations)}

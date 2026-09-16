"""CSE simulation of the posted external NC file, never internal toolpaths."""

import json


def machine_time_seconds(value):
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def save_external_nc_reference(part, nc):
    """Persist channel 1's article NC in Program Manager for manual reopening."""
    from .variant import _save_part

    manager = part.KinematicConfigurator.CreateNcProgramManagerBuilder()
    try:
        source = manager.GetExternalFileSource()
        previous = source.GetMainProgram("1")
        if previous is not None:
            source.DeleteProgram(previous)
        source.AddMainProgram("1", str(nc))
        manager.Commit()
    finally:
        manager.Destroy()
    # Save before CSE moves the machine; only save the article setup itself.
    _save_part(part)


def simulate_article(request):
    import NXOpen
    import NXOpen.CAM
    import NXOpen.SIM
    from .assembly.paths import request_paths
    from .setup import common
    from nc_release import invalidate_release, nc_hash

    paths = request_paths(request)
    invalidate_release(paths.item_dir)
    nc = paths.item_dir / f"{paths.name}-SETUP.min"
    fingerprint = nc_hash(nc)
    session = NXOpen.Session.GetSession()
    common.load_product_parts(session, paths)
    part = common.open_display(session, paths.part("SETUP"), paths.custom_dir)
    print(f"SIM: application={session.ApplicationName}, batch={session.IsBatch}", flush=True)
    session.ApplicationSwitchImmediate("UG_APP_MANUFACTURING")
    if not session.IsCamSessionInitialized():
        session.CreateCamSession()
    save_external_nc_reference(part, nc)
    session.SetUndoMark(NXOpen.Session.MarkVisibility.Visible, "External NC simulation")
    session.BeginTaskEnvironment()
    panel = None
    completed = False

    def on_end(*args):
        nonlocal completed
        completed = True
        print("SIM: reached end of external NC program", flush=True)

    def on_stop(*args):
        print("SIM: stopped", flush=True)

    try:
        configurator = part.KinematicConfigurator
        channels = configurator.CreateNcChannelSelectionData()
        channels.AssignFile("1", str(nc))
        panel = configurator.CreateIsvControlPanelBuilder(
            NXOpen.SIM.IsvControlPanelBuilder.VisualizationType.MachineCodeSimulateCse, channels)
        options = panel.SimulationOptionsBuilder
        # CSE must also suppress NC-panel updates in run_journal; SuppressGraphics
        # alone stalls at the first tool change. This does not disable checking.
        options.SimulationDisplay = NXOpen.CAM.SimulationOptionsBuilder.SimulationDisplayMode.SuppressAll
        options.EnableMachineCollision = True
        options.EnableMaterialRemoval = True
        options.ToolIpwCollision = True
        options.ToolPartCollision = True
        options.StopOnCollision = True
        options.StopOnLimitViolation = True
        options.StopOnRapidThroughIpw = True
        options.StopOnM1 = False
        options.StopOnHistoryBuffer = False
        options.CheckLimitViolation = True
        options.MaxLengthIncr = 1.0
        options.Commit()
        panel.ApplySimulationOptions()
        print(f"SIM: checks machine={options.EnableMachineCollision}, material={options.EnableMaterialRemoval}, "
              f"tool/IPW={options.ToolIpwCollision}, tool/part={options.ToolPartCollision}, "
              f"limits={options.CheckLimitViolation}", flush=True)
        panel.SetSpeed(10)
        panel.AddSimEnd(on_end)
        panel.AddSimStart(lambda *args: print(f"SIM: start event {args}", flush=True))
        panel.AddSimStop(on_stop)
        print(f"SIM: CSE step-mode={panel.GetSingleStepMode()}, time={panel.MachineTime}", flush=True)
        print(f"SIM: external NC {nc}; collision/part/IPW checks enabled", flush=True)
        panel.PlayForward()
        print(f"SIM: PlayForward returned at {panel.MachineTime}", flush=True)
        counts, details, controller_messages = {}, [], []
        for name in ("Controller", "Limit", "Collision", "Gouge", "Singularity"):
            kind = getattr(NXOpen.SIM.IsvControlPanelBuilder.DetailType, name)
            count = panel.GetDetailCount(kind)
            if name != "Controller":
                counts[name] = count
            for index in range(count):
                found, machine_time, description, line, program, channel = panel.GetDetail(kind, index)
                if found:
                    target = controller_messages if name == "Controller" else details
                    target.append(dict(type=name, description=description, line=line, program=program, channel=channel))
        result = dict(mode="external_nc", completed=completed, counts=counts, details=details,
                      controller_messages=controller_messages,
                      nc_sha256=fingerprint, nc_program=str(nc), machine_time=panel.MachineTime,
                      passed=completed and not any(counts.values()) and nc_hash(nc) == fingerprint)
        print("SIM: " + json.dumps(result), flush=True)
    finally:
        if panel is not None:
            if not completed:
                panel.Stop()
            panel.Destroy()
        session.DeleteUndoMarksSetInTaskEnvironment()
        session.EndTaskEnvironment()
        common.close_setup(part)
    (paths.item_dir / "simulation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    if not result["passed"]:
        reason = ("NC-bestand is tijdens de simulatie gewijzigd." if nc_hash(nc) != fingerprint else "") or "; ".join(d["description"] for d in details[:5]) or "; ".join(
            d["description"] for d in controller_messages if "error" in d["description"].lower()
        ) or "Het einde van het externe NC-programma is niet bereikt."
        raise RuntimeError(f"Externe NC-simulatie niet geslaagd (volledig afgerond={completed}): {reason}")
    return {"setup": str(paths.part("SETUP")), "simulation_passed": True, "nc_program": str(nc),
            "simulation_time_seconds": machine_time_seconds(result["machine_time"])}

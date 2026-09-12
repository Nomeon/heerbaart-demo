"""Root nx_setup_step3 stage 1: template, product, and three device assemblies."""

import NXOpen

from . import common as setup


def run(paths):
    session = NXOpen.Session.GetSession()
    input_file = paths.part("ASSY")
    input_part = setup.open_base(session, input_file)
    blank_part = setup.open_base(session, paths.part("BLANK"))
    spanning_diameter = setup.determine_spanning_diameter(blank_part)[0]
    _lower, _upper, device_file, _jaw_file = setup.select_jaw(spanning_diameter, paths.device_root)
    machine_part = setup.open_display(session, paths.template, paths.custom_dir)
    # All subsequent edits belong to this setup, never to the machine template.
    setup.save_setup(machine_part, paths.work_dir / f"{paths.name}_SETUP_LOADING.prt")
    assy_component, status = machine_part.ComponentAssembly.AddMasterPartComponent(
        input_part, "NONE", input_file.stem,
        NXOpen.Point3d(0.0, 0.0, 700.0), setup.identity_matrix(NXOpen), -1,
    )
    setup.dispose(status)
    if assy_component is None:
        raise RuntimeError("NX did not add the product ASSY")

    _z, _base_assy, base_jaws = setup.find_left_chuck_and_jaws(machine_part)
    setup.open_base(session, paths.device_root / "__Components" / "GBK_400_out.prt")
    device_part = setup.open_base(session, device_file)
    setup.dispose(session.Parts.EnsurePartsLoadedFully([device_part], True))
    for index, base_jaw in enumerate(base_jaws, start=1):
        base_point, base_matrix = base_jaw.GetPosition()
        device_component = setup.add_component(
            machine_part.ComponentAssembly, device_part,
            f"{device_file.stem}_JAW{index}", base_point, base_matrix,
        )
        if hasattr(device_component, "LoadThisPartFully"):
            setup.dispose(device_component.LoadThisPartFully())
        children = [
            child for child in device_component.GetChildren()
            if "_PART" in child.DisplayName.upper()
        ]
        if len(children) != 1:
            raise RuntimeError(f"Device {index} must contain exactly one nested _PART")

    machine_part = setup.save_reopen(
        machine_part, paths.work_dir / f"{paths.name}_DEVICES_LOADED.prt", paths.custom_dir
    )
    setup.publish_setup(machine_part, paths, "load")
    # The caller must now terminate NX and invoke constraints in a fresh process.

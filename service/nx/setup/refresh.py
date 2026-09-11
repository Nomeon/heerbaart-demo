"""Refresh a cloned workholding setup without reconstructing its machine or CAM tree."""

import NXOpen

from . import common as setup
from . import axis_touch, blank_body, jaws, main_body, main_curve, product, stops
from .position_checks import validate_flow4_reopen


def run(paths):
    session = NXOpen.Session.GetSession()
    session.SetUndoMark(NXOpen.Session.MarkVisibility.Visible, "Refresh cloned setup")
    setup.load_product_parts(session, paths)
    blank = setup.open_base(session, paths.part("BLANK"))
    diameter = setup.determine_spanning_diameter(blank)[0]
    largest_diameter = main_body.determine_blank_gripping_diameter(blank)
    _lower, _upper, device_file, _jaw = setup.select_jaw(diameter, paths.device_root)
    machine = setup.open_display(session, paths.part("SETUP"))
    occurrence = setup.require_local_product(machine, paths)
    was_hidden = bool(occurrence.IsBlanked)
    existing_jaws = [
        child for child in machine.ComponentAssembly.RootComponent.GetChildren()
        if setup.prototype_path(child) == device_file.resolve()
    ]
    if len(existing_jaws) != 3:
        raise RuntimeError("Refresh cannot replace the cloned jaw device; the new diameter requires the same library device")
    generated_names = {"ELSTER_AXIS_TOUCH", "FLOW5_AXIAL_TOUCH", "FLOW5_TOP_PARALLEL"}
    existing_names = {
        constraint.Name for constraint, _owner in product._all_component_constraints(machine)
        if constraint.OwningPart.Tag == machine.Tag and not constraint.Suppressed
    }
    if not generated_names.issubset(existing_names):
        raise RuntimeError("Refresh requires a completed extracted baseline setup with its generated positioning constraints")

    # Never call load, holder mounting, product substitution, or initial p3 copying here.
    input_file = paths.part("ASSY")
    product._delete_product_center_constraints(machine, input_file)
    expected_p3, expected_radius = jaws.refresh_jaw_parameter(session, machine, diameter, paths.device_root)
    machine = product._save_reopen_product_setup(machine, input_file, paths.work_dir)
    occurrence = setup.require_local_product(machine, paths)
    occurrence.Unblank()
    main_curve.move_flow6_main_curve_to_cad4cam_far_face(machine, input_file)
    axis_touch.apply_journal_blank_touch_constraint(session, machine, input_file, paths.device_root)
    stops.apply_product_stop_and_top(machine, input_file, device_file)
    main_curve.position_flow6_main_curve_after_product_setup(machine, input_file)
    main_body.apply_flow6_main_outside_and_linked_body(session, machine, input_file, largest_diameter)
    blank_body.apply_flow6_main_inside_and_blank_link(session, machine, input_file, hide_history=False)
    if was_hidden:
        occurrence.Blank()
    session.UpdateManager.DoUpdate(session.NewestVisibleUndoMark)

    final_file = paths.work_dir / f"{paths.name}_REFRESH_FINAL.prt"
    machine = setup.save_reopen(machine, final_file)
    setup.require_local_product(machine, paths)
    validate_flow4_reopen(machine, input_file, device_file, expected_p3, expected_radius, expect_journal_touch=True)
    stops.validate_product_stop_and_top(machine, input_file, device_file)
    main_curve.validate_flow6_main_curve(machine, input_file)
    main_body.validate_flow6_main_outside_and_linked_body(session, machine, input_file, largest_diameter)
    blank_body.validate_flow6_main_inside_and_blank_link(session, machine, input_file, check_history=False)
    setup.close_setup(machine)
    final_file.replace(paths.part("SETUP"))
    return {"setup": str(paths.part("SETUP")), "jaw_p3": expected_p3}

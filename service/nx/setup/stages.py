"""Explicit initial Flow 2, Flow 5 and Flow 6 sequences, with native reopen points."""

import NXOpen
import NXOpen.Assemblies

from . import common as setup
from . import axis_touch, blank_body, holders, jaws, main_body, main_curve
from . import position_checks, product, stops, view


def attach_holders(paths):
    session = NXOpen.Session.GetSession()
    blank = setup.open_base(session, paths.part("BLANK"))
    diameter = setup.determine_spanning_diameter(blank)[0]
    _lower, _upper, device_file, _jaw = setup.select_jaw(diameter, paths.device_root)
    machine = setup.open_display(session, paths.part("SETUP"), paths.custom_dir)
    existing = [
        child for child in machine.ComponentAssembly.RootComponent.GetChildren()
        if child.DisplayName.upper() == device_file.stem.upper()
    ]
    if len(existing) != 3:
        raise RuntimeError("The holders stage requires the three existing Flow 1 jaws")
    holders.add_existing_jaws_to_main_holders(session, machine, device_file, existing)
    setup.publish_setup(machine, paths, "holders")


def position_and_reference(paths, references):
    session = NXOpen.Session.GetSession()
    input_file = paths.part("ASSY")
    blank = setup.open_base(session, paths.part("BLANK"))
    diameter = setup.determine_spanning_diameter(blank)[0]
    largest_diameter = main_body.determine_blank_gripping_diameter(blank) if references else None
    _lower, _upper, device_file, _jaw = setup.select_jaw(diameter, paths.device_root)
    machine = setup.open_display(session, paths.part("SETUP"), paths.custom_dir)
    setup.require_local_product(machine, paths)
    existing = [
        child for child in machine.ComponentAssembly.RootComponent.GetChildren()
        if child.DisplayName.upper() == device_file.stem.upper()
    ]
    if len(existing) != 3:
        raise RuntimeError("Positioning requires the three existing jaw occurrences")
    holders.add_existing_jaws_to_main_holders(
        session, machine, device_file, existing, allow_existing=True
    )
    product._delete_product_center_constraints(machine, input_file)
    expected_p3, expected_radius = jaws.apply_journal_diameter_parameter(
        session, machine, diameter, device_file, paths.device_root
    )
    # The active source's substitution branch is unnecessary for a local ASSY.
    # Keep its occurrence intact and retain its positioning/reopen sequence.
    product._move_product_to_chuck_midpoint(machine, input_file)
    machine = product._save_reopen_product_setup(machine, input_file, paths.work_dir, paths.custom_dir)
    product._delete_product_center_constraints(machine, input_file)
    view.restore_input_product_visibility(machine, input_file)
    view.apply_saved_view_visibility(machine, input_file)
    view.apply_input_blank_transparency(machine, input_file)
    view.apply_journal_final_view(machine, NXOpen)

    machine = setup.save_reopen(machine, paths.work_dir / f"{paths.name}_POSITION_STAGED.prt", paths.custom_dir)
    setup.load_product_parts(session, paths)
    final_product = setup.require_local_product(machine, paths)
    opened = machine.ComponentAssembly.OpenComponents(
        NXOpen.Assemblies.ComponentAssemblyOpenOption.WholeAssembly, [final_product]
    )
    setup.dispose(opened[0] if isinstance(opened, tuple) else opened)
    final_product.UpdateStructure([final_product], 2, True)
    final_blank = setup.find_product_component(final_product, paths.part("BLANK").stem)
    opened = machine.ComponentAssembly.OpenComponents(
        NXOpen.Assemblies.ComponentAssemblyOpenOption.ComponentOnly, [final_blank]
    )
    setup.dispose(opened[0] if isinstance(opened, tuple) else opened)
    final_blank.UpdateStructure([final_blank], 2, True)
    jaws._journal_base_jaw_components(machine, paths.device_root)
    machine = product._save_reopen_product_setup(machine, input_file, paths.work_dir, paths.custom_dir)
    product._delete_product_center_constraints(machine, input_file)
    if references:
        # WAVE must precede the final parallel constraint, as in active Flow 6.
        main_curve.move_flow6_main_curve_to_cad4cam_far_face(machine, input_file)
    axis_touch.apply_journal_blank_touch_constraint(session, machine, input_file, paths.device_root)
    stops.apply_product_stop_and_top(machine, input_file, device_file)
    if references:
        main_curve.position_flow6_main_curve_after_product_setup(machine, input_file)
        main_body.apply_flow6_main_outside_and_linked_body(session, machine, input_file, largest_diameter)
        blank_body.apply_flow6_main_inside_and_blank_link(session, machine, input_file)
        view.hide_flow6_input_assembly(machine, input_file)

    label = "REFERENCES" if references else "POSITION"
    final_file = paths.work_dir / f"{paths.name}_{label}_FINAL.prt"
    machine = setup.save_reopen(machine, final_file, paths.custom_dir)
    position_checks.validate_flow4_reopen(
        machine, input_file, device_file, expected_p3, expected_radius, expect_journal_touch=True
    )
    stops.validate_product_stop_and_top(machine, input_file, device_file)
    if references:
        main_curve.validate_flow6_main_curve(machine, input_file)
        main_body.validate_flow6_main_outside_and_linked_body(session, machine, input_file, largest_diameter)
        blank_body.validate_flow6_main_inside_and_blank_link(session, machine, input_file)
        view.validate_flow6_input_assembly_hidden(machine, input_file)
    setup.close_setup(machine)
    final_file.replace(paths.part("SETUP"))

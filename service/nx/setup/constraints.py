"""Active builders extracted from Setup_Generator/nx_setup_constraints_stage2.py."""

import NXOpen
import NXOpen.Positioning

from . import common as setup
from . import view

def run(paths):
    input_file = paths.part("ASSY")
    blank_file = paths.part("BLANK")
    session = NXOpen.Session.GetSession()
    blank_part = setup.open_base(session, blank_file)
    spanning_diameter, _z_start, _z_end, _diameter_z = setup.determine_spanning_diameter(blank_part)
    lower, upper, device_file, jaw_file = setup.select_jaw(spanning_diameter, paths.device_root)

    working_file = paths.part("SETUP")
    if not working_file.exists():
        raise RuntimeError(f"Stage 1 tussenbestand ontbreekt: {working_file}")
    machine_part = setup.open_display(session, working_file, paths.custom_dir)

    setup.open_base(session, paths.device_root / "__Components" / "GBK_400_out.prt")
    device_part = setup.open_base(session, device_file)
    jaw_part = setup.open_base(session, jaw_file)
    session.Parts.EnsurePartsLoadedFully([machine_part, device_part, jaw_part], True)

    _z, base_assy, base_jaws = setup.find_left_chuck_and_jaws(machine_part)
    outer_chuck = setup.find_outer_chuck_for_assy(machine_part, base_assy)
    journal_base_assy = setup.find_component_occurrence(outer_chuck, base_assy.DisplayName)
    # De drie GBK-occurrences hebben dezelfde naam. Een enkele FindObject()
    # retourneert daarom driemaal hetzelfde eerste bek. Haal alle directe
    # occurrences op en koppel ze één-op-één aan de fysieke basisbekposities.
    all_journal_base_jaws = setup.find_component_occurrences(
        journal_base_assy, base_jaws[0].DisplayName
    )
    journal_base_jaws = setup.match_occurrences_by_position(
        base_jaws, all_journal_base_jaws
    )
    baseline_constraints = setup.snapshot_constraint_baseline(machine_part)

    root = machine_part.ComponentAssembly.RootComponent
    device_components = [
        root.FindObject(f"COMPONENT {device_file.stem} {index}")
        for index in (1, 2, 3)
    ]
    # NX kent de drie device-occurrences na heropenen in occurrence-indexvolgorde
    # toe, niet in de volgorde waarin ze fysiek rond de chuck staan. Koppel ze
    # daarom op positie aan de basisbekken en werk daarna in fysieke slotvolgorde.
    device_components_by_base = setup.match_occurrences_by_position(
        journal_base_jaws, device_components
    )
    jaw_components_by_base = [
        setup.find_component_occurrence(device_component, f"{device_file.stem}_PART")
        for device_component in device_components_by_base
    ]
    for component in jaw_components_by_base:
        if hasattr(component, "LoadThisPartFully"):
            component.LoadThisPartFully()

    generated_constraints = []
    journal_touch_faces = ((55, 303), (48, 283), (62, 303))
    for jaw_index, (jaw_component, base_jaw) in enumerate(zip(
        jaw_components_by_base, journal_base_jaws
    )):
        base_point, _base_matrix = base_jaw.GetPosition()
        jaw_vector, base_vector = setup.jaw_perpendicular_vectors(base_point, NXOpen)
        jaw_hole_1 = setup.find_face(jaw_component, [
            "PROTO#.Features|UNPARAMETERIZED_FEATURE(1)|FACE 40 {(-10,27,41.0000000000198) UNPARAMETERIZED_FEATURE(1)}",
        ])
        jaw_hole_2 = setup.find_face(jaw_component, [
            "PROTO#.Features|UNPARAMETERIZED_FEATURE(1)|FACE 83 {(-10,-27,28.5) UNPARAMETERIZED_FEATURE(1)}",
        ])
        base_hole_1 = setup.find_face(base_jaw, [
            "PROTO#.Features|UNPARAMETERIZED_FEATURE(0)|FACE 616 {(-27,-5.1,-11.7) UNPARAMETERIZED_FEATURE(0)}",
        ])
        base_hole_2 = setup.find_face(base_jaw, [
            "PROTO#.Features|UNPARAMETERIZED_FEATURE(0)|FACE 613 {(27,-5.1,-11.7) UNPARAMETERIZED_FEATURE(0)}",
        ])
        generated_constraints.append(setup.apply_one_journal_constraint(
            machine_part, NXOpen, session, jaw_component,
            lambda positioner: setup.add_journal_align_lock(
                positioner, NXOpen, jaw_component, jaw_hole_1,
                outer_chuck, base_hole_1, jaw_vector, base_vector, machine_part,
            ),
        ))
        generated_constraints.append(setup.apply_one_journal_constraint(
            machine_part, NXOpen, session, jaw_component,
            lambda positioner: setup.add_journal_align_lock(
                positioner, NXOpen, jaw_component, jaw_hole_2,
                outer_chuck, base_hole_2, jaw_vector, base_vector, machine_part,
            ),
        ))

        touch_jaw_face, touch_base_face = journal_touch_faces[jaw_index]
        jaw_touch = setup.find_face(jaw_component, [{
            55: "PROTO#.Features|UNPARAMETERIZED_FEATURE(1)|FACE 55 {(15.5,32,6) UNPARAMETERIZED_FEATURE(1)}",
            48: "PROTO#.Features|UNPARAMETERIZED_FEATURE(1)|FACE 48 {(15.5,-29.5,6) UNPARAMETERIZED_FEATURE(1)}",
            62: "PROTO#.Features|UNPARAMETERIZED_FEATURE(1)|FACE 62 {(-15.5,32,6) UNPARAMETERIZED_FEATURE(1)}",
        }[touch_jaw_face]])
        base_touch = setup.find_face(base_jaw, [{
            303: "PROTO#.Features|UNPARAMETERIZED_FEATURE(0)|FACE 303 {(-28,-11.75,-0) UNPARAMETERIZED_FEATURE(0)}",
            283: "PROTO#.Features|UNPARAMETERIZED_FEATURE(0)|FACE 283 {(28,11.75,-0) UNPARAMETERIZED_FEATURE(0)}",
        }[touch_base_face]])
        generated_constraints.append(setup.apply_one_journal_constraint(
            machine_part, NXOpen, session, jaw_component,
            lambda positioner: setup.add_journal_touch(
                positioner, NXOpen, jaw_component, jaw_touch,
                outer_chuck, base_touch, machine_part,
            ),
        ))

    if len(generated_constraints) != 9:
        raise RuntimeError(f"Stage 2 maakte niet exact 9 constraints: {len(generated_constraints)}")

    # Validate the persisted constraint state only after the native save/reopen.
    verification = paths.work_dir / f"{paths.name}_CONSTRAINTS_VERIFIED.prt"
    machine_part = setup.save_reopen(machine_part, verification, paths.custom_dir)
    setup.open_base(session, device_file)
    setup.open_base(session, jaw_file)
    session.Parts.EnsurePartsLoadedFully([machine_part], True)

    setup.validate_all_assembly_constraints(
        machine_part, baseline_constraints, generated_constraints
    )
    view.apply_saved_view_visibility(machine_part, input_file)
    view.apply_journal_final_view(machine_part, NXOpen)
    setup.publish_setup(machine_part, paths, "constraints")
    print(f"Stage 2 opgeslagen: {paths.part('SETUP')}", flush=True)
    print(f"Spandiameter: {spanning_diameter:.3f} mm; device: {device_file.name}", flush=True)

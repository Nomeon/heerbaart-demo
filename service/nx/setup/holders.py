"""Flow 2 holder attachment, including the active Flow 5/6 reuse check."""

import NXOpen
import NXOpen.CAM

from . import common as setup


def find_cam_member(parent, name):
    matches = [
        member for member in parent.GetMembers()
        if member.Name.upper() == name.upper()
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"CAM-member {name} niet uniek onder {parent.Name}: "
            f"{[member.Name for member in matches]}"
        )
    return matches[0]



def position_text(component):
    point, _matrix = component.GetPosition()
    return f"({float(point.X):.3f},{float(point.Y):.3f},{float(point.Z):.3f})"



def component_position_key(component):
    point, _matrix = component.GetPosition()
    return tuple(round(float(getattr(point, axis)), 6) for axis in ("X", "Y", "Z"))



def snapshot_constraint_states(machine_part):
    states = {}
    for tag, (constraint, owner) in setup.snapshot_constraint_baseline(machine_part).items():
        states[tag] = (str(constraint.GetConstraintStatus()), owner)
    return states



def add_existing_jaws_to_main_holders(session, machine_part, device_file, existing_jaws, allow_existing=False):
    """Populate holders while retaining the existing assembly occurrences.

    NX2512 exposes holder population through RetrieveDeviceAndMount, which
    creates a temporary occurrence. The existing three jaws are never removed
    or repositioned: only the temporary mount occurrences are discarded after
    the CAM holder references have been created.
    """
    if not session.IsCamSessionInitialized():
        session.CreateCamSession()
    cam_setup = machine_part.CAMSetup
    machine_root = cam_setup.GetRoot(NXOpen.CAM.CAMSetupView.MachineTool)
    main_chuck = find_cam_member(machine_root, "MAIN_CHUCK")
    main_device = find_cam_member(main_chuck, "KNCS-N_400-128-A8_OUT")
    holders = [
        find_cam_member(main_device, f"HOLDER_JAW{index}")
        for index in (1, 2, 3)
    ]
    existing_holder_members = [
        [member.Name for member in holder.GetMembers()]
        for holder in holders
    ]
    expected_members = [
        [device_file.stem],
        [f"{device_file.stem}_1"],
        [f"{device_file.stem}_2"],
    ]
    if existing_holder_members != expected_members:
        if any(existing_holder_members):
            raise RuntimeError(
                "MAIN_CHUCK HOLDER_JAW1/2/3 zijn gedeeltelijk gevuld; "
                "er wordt niets gewijzigd: "
                f"{existing_holder_members}"
            )
    else:
        if not allow_existing:
            raise RuntimeError("The initial holders stage requires empty MAIN holders")
        print(
            "Flow 3 hergebruikt de bestaande MAIN_CHUCK holder-members; "
            "er worden geen tijdelijke jaws geladen.",
            flush=True,
        )
        return

    assembly = machine_part.ComponentAssembly
    before_root = list(assembly.RootComponent.GetChildren())
    before_tags = {component.Tag for component in before_root}
    before_positions = {
        component.Tag: component_position_key(component)
        for component in existing_jaws
    }
    before_constraints = snapshot_constraint_states(machine_part)
    temporary_components = []

    for holder in holders:
        result = cam_setup.RetrieveDeviceAndMount(device_file.stem, holder)
        if not isinstance(result, tuple):
            raise RuntimeError(f"Mount op {holder.Name} gaf geen tuple-resultaat.")
        candidates = [
            component for component in assembly.RootComponent.GetChildren()
            if component.DisplayName.upper() == device_file.stem.upper()
            and component.Tag not in before_tags
            and component.Tag not in {item.Tag for item in temporary_components}
        ]
        if len(candidates) != 1:
            raise RuntimeError(
                f"Mount op {holder.Name} maakte niet exact één tijdelijke occurrence: "
                f"{len(candidates)}."
            )
        temporary_components.append(candidates[0])

    holder_members = [
        [member.Name for member in holder.GetMembers()]
        for holder in holders
    ]
    if any(len(names) != 1 for names in holder_members):
        raise RuntimeError(f"Niet elke MAIN-holder bevat exact één jaw: {holder_members}")

    for component in temporary_components:
        assembly.RemoveComponent(component)
    session.UpdateManager.DoUpdate(session.NewestVisibleUndoMark)

    final_root = list(assembly.RootComponent.GetChildren())
    final_jaws = [
        component for component in final_root
        if component.DisplayName.upper() == device_file.stem.upper()
    ]
    if len(final_jaws) != 3 or {component.Tag for component in final_jaws} != {
        component.Tag for component in existing_jaws
    }:
        raise RuntimeError(
            "De tijdelijke mounts zijn niet volledig verwijderd of de bestaande "
            f"jaws zijn gewijzigd: {len(final_jaws)} occurrences."
        )
    for component in final_jaws:
        if component_position_key(component) != before_positions[component.Tag]:
            raise RuntimeError(
                f"Bestaande jaw {component.DisplayName} is verplaatst: "
                f"{position_text(component)}."
            )

    after_constraints = snapshot_constraint_states(machine_part)
    if after_constraints != before_constraints:
        raise RuntimeError(
            "De holder-stap heeft de bestaande constraints/statussen gewijzigd. "
            f"voor={before_constraints}, na={after_constraints}"
        )
    final_members = [
        [member.Name for member in holder.GetMembers()]
        for holder in holders
    ]
    print(
        "Flow 2 holder-koppeling gecontroleerd: bestaande jaws behouden op "
        f"{[position_text(component) for component in final_jaws]}; "
        f"holders={final_members}; constraints={len(after_constraints)}.",
        flush=True,
    )

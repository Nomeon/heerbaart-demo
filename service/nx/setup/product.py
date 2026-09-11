"""Active workholding builders extracted from Setup_Generator/flow6/flow6_attach_holders.py."""

import NXOpen
import NXOpen.Assemblies
import NXOpen.Positioning

from . import common as setup


def _all_component_constraints(machine_part):
    """Yield every assembly constraint together with its component owner."""
    stack = [machine_part.ComponentAssembly.RootComponent]
    seen = set()
    while stack:
        owner = stack.pop()
        try:
            constraints = owner.GetConstraints()
        except Exception:
            constraints = []
        for constraint in constraints:
            if constraint.Tag in seen:
                continue
            seen.add(constraint.Tag)
            yield constraint, owner
        try:
            stack.extend(owner.GetChildren())
        except Exception:
            pass



def _product_center_constraints(machine_part, input_file):
    """Stable generated names survive native clone occurrence-name remapping."""
    return [
        constraint for constraint, _owner in _all_component_constraints(machine_part)
        if constraint.Name == "ELSTER_AXIS_TOUCH"
        and constraint.OwningPart.Tag == machine_part.Tag
    ]



def _journal_product_touch_constraints(machine_part, input_file):
    return [
        constraint for constraint in _product_center_constraints(machine_part, input_file)
        if not constraint.Suppressed
        and constraint.ConstraintType == NXOpen.Positioning.Constraint.Type.Touch
    ]



def _delete_product_center_constraints(machine_part, input_file):
    """Remove only obsolete product-to-chuck center relations."""
    candidates = _product_center_constraints(machine_part, input_file)
    seen = {c.Tag for c in candidates}
    for constraint, _owner in _all_component_constraints(machine_part):
        if (constraint.Name in {"FLOW5_AXIAL_TOUCH", "FLOW5_TOP_PARALLEL"}
                and constraint.Tag not in seen):
            candidates.append(constraint)
            seen.add(constraint.Tag)
    if not candidates:
        return
    for constraint in candidates:
        setup.require_setup_owned(constraint, machine_part)
    session = NXOpen.Session.GetSession()
    session.UpdateManager.AddObjectsToDeleteList(candidates)
    session.UpdateManager.DoUpdate(session.NewestVisibleUndoMark)
    print(
        "Flow 4: oude product-centerconstraint(s) verwijderd vóór de p3-stap; "
        f"aantal={len(candidates)}.",
        flush=True,
    )



def _move_product_to_chuck_midpoint(machine_part, input_file):
    """Place the product occurrence at the axial midpoint of the two chucks."""
    session = NXOpen.Session.GetSession()
    root = machine_part.ComponentAssembly.RootComponent
    product = setup.find_product_component(root, input_file.stem)
    chucks = [
        component
        for component in root.GetChildren()
        if component.DisplayName.upper() == "SMW_KNCS-N_400-128-A8_OUT"
    ]
    if len(chucks) != 2:
        raise RuntimeError(
            "Product-midpoint verwacht exact twee klauwplaten; "
            f"gevonden: {len(chucks)}."
        )
    chuck_z = [float(component.GetPosition()[0].Z) for component in chucks]
    midpoint_z = sum(chuck_z) / 2.0
    current_point, _current_matrix = product.GetPosition()
    delta_z = midpoint_z - float(current_point.Z)
    if abs(delta_z) > 1e-6:
        positioner = machine_part.ComponentAssembly.Positioner
        arrangement = machine_part.ComponentAssembly.Arrangements.FindObject(
            "Arrangement 1"
        )
        positioner.PrimaryArrangement = arrangement
        positioner.BeginMoveComponent()
        network = None
        try:
            network = positioner.EstablishNetwork()
            network.NetworkArrangementsMode = (
                NXOpen.Positioning.ComponentNetwork.ArrangementsMode.Existing
            )
            network.DisplayComponent = None
            network.MoveObjectsState = True
            network.AddMovableObject(product)
            network.SetMovingGroup([product])
            network.RemoveAllConstraints()
            network.BeginDrag()
            network.DragByTranslation(NXOpen.Vector3d(0.0, 0.0, delta_z))
            network.EndDrag()
            network.ApplyToModel()
        finally:
            if network is not None:
                try:
                    positioner.ClearNetwork()
                except Exception:
                    pass
            try:
                positioner.EndMoveComponent()
            except Exception:
                pass
            positioner.PrimaryArrangement = None
    session.UpdateManager.DoUpdate(session.NewestVisibleUndoMark)
    actual_point, _actual_matrix = product.GetPosition()
    if abs(float(actual_point.Z) - midpoint_z) > 1e-5:
        raise RuntimeError(
            f"Product staat op Z={actual_point.Z:.6f}; "
            f"verwacht midden tussen klauwplaten Z={midpoint_z:.6f}."
        )
    print(
        "Flow 4 productpositie: midden tussen MAIN_CHUCK en SUB_CHUCK; "
        f"chuck-Z={[round(value, 6) for value in chuck_z]}, "
        f"product-Z={actual_point.Z:.6f}.",
        flush=True,
    )
    return midpoint_z



def _save_reopen_product_setup(machine_part, input_file, work_dir):
    """Persist the p3/input state and reload it for the final checks."""
    session = NXOpen.Session.GetSession()
    center_stage = (
        work_dir /
        f"{input_file.stem}_FLOW4_CENTER_STAGE.prt"
    )
    center_stage.parent.mkdir(parents=True, exist_ok=True)
    reopened = setup.save_reopen(machine_part, center_stage)
    session.Parts.EnsurePartsLoadedFully([reopened], True)
    input_part = setup.open_base(session, input_file)
    setup.dispose(session.Parts.EnsurePartsLoadedFully([input_part], True))
    root = reopened.ComponentAssembly.RootComponent
    product = setup.find_product_component(root, input_file.stem)
    opened = reopened.ComponentAssembly.OpenComponents(
        NXOpen.Assemblies.ComponentAssemblyOpenOption.WholeAssembly,
        [product],
    )
    setup.dispose(opened[0] if isinstance(opened, tuple) else opened)
    product.UpdateStructure([product], 2, True)
    blank_stem = input_file.stem.removesuffix("_ASSY") + "_BLANK"
    blank = setup.find_product_component(product, blank_stem)
    opened = reopened.ComponentAssembly.OpenComponents(
        NXOpen.Assemblies.ComponentAssemblyOpenOption.ComponentOnly,
        [blank],
    )
    setup.dispose(opened[0] if isinstance(opened, tuple) else opened)
    blank.UpdateStructure([blank], 2, True)
    session.Parts.EnsurePartsLoadedFully([reopened], True)
    print(
        "Flow 4 product/input-state opgeslagen en opnieuw geopend voor de "
        "eindcontrole.",
        flush=True,
    )
    return reopened

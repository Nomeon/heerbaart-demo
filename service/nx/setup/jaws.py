"""Active workholding builders extracted from Setup_Generator/flow6/flow6_attach_holders.py."""

import math
import re

import NXOpen
import NXOpen.Assemblies
import NXOpen.Positioning

from . import common as setup

LOWEST_GRIP_EDGE_DIAMETER = 335.714642124


def _journal_base_jaw_components(machine_part, device_root):
    """Unpack the existing chuck occurrence exactly as in journal.cs."""
    session = NXOpen.Session.GetSession()
    library_paths = [
        device_root
        / "SMW_KNCS-N_400-128-A8_OUT"
        / "SMW_KNCS-N_400-128-A8_OUT.prt",
        device_root
        / "SMW_KNCS-N_400-128-A8_OUT"
        / "SMW_KNCS-N_400-128-A8_out_assy.prt",
        device_root / "__Components" / "GBK_400_out.prt",
        device_root / "__Components" / "KNCS-N_400-128_chuck.prt",
        device_root / "__Components" / "KNCS-N_400-128_adapter.prt",
    ]
    library_parts = []
    for library_path in library_paths:
        try:
            library_parts.append(setup.open_base(session, library_path))
        except Exception as error:
            if "File already exists" not in str(error):
                raise
            # A prior center-constraint step may already have opened the same
            # NX library part.  It is already usable in this session; opening
            # it a second time would abort the run.
    session.Parts.EnsurePartsLoadedFully([machine_part, *library_parts], True)
    root = machine_part.ComponentAssembly.RootComponent
    outer = root.FindObject("COMPONENT SMW_KNCS-N_400-128-A8_OUT 2")
    opened = machine_part.ComponentAssembly.OpenComponents(
        NXOpen.Assemblies.ComponentAssembly.OpenOption.WholeAssembly, [outer]
    )
    if isinstance(opened, tuple):
        setup.dispose(opened[0])
    outer.UpdateStructure([outer], 2, True)
    chuck_assy = outer.FindObject(
        "COMPONENT SMW_KNCS-N_400-128-A8_out_assy 1"
    )
    chuck_assy.UpdateStructure([chuck_assy], 2, True)
    adapter = chuck_assy.FindObject(
        "COMPONENT KNCS-N_400-128_adapter 1"
    )
    opened = machine_part.ComponentAssembly.OpenComponents(
        NXOpen.Assemblies.ComponentAssemblyOpenOption.ComponentOnly,
        [adapter],
    )
    if isinstance(opened, tuple):
        setup.dispose(opened[0])
    base_jaws = [
        chuck_assy.FindObject(f"COMPONENT GBK_400_out {index}")
        for index in (1, 2, 3)
    ]
    for base_jaw in base_jaws:
        opened = machine_part.ComponentAssembly.OpenComponents(
            NXOpen.Assemblies.ComponentAssembly.OpenOption.ComponentOnly,
            [base_jaw],
        )
        if isinstance(opened, tuple):
            setup.dispose(opened[0])
        # This is deliberately the same local override used in the journal;
        # it does not edit GBK_400_out.prt or the chuck library assembly.
        try:
            base_jaw.EstablishPositionOverride(None)
        except Exception as error:
            # A rerun of Flow 4 starts from its own already-local override.
            # Keep that override; never create a second occurrence or edit the
            # library component.
            if "override" not in str(error).lower() and "already" not in str(error).lower():
                raise
    return outer, chuck_assy, base_jaws



def _restore_p3_start(machine_part, base_jaws):
    """Use the recorded 75 mm source without writing a library expression."""
    constraints = {
        constraint.Tag: constraint
        for base_jaw in base_jaws for constraint in base_jaw.GetConstraints()
    }
    source_constraints = [
        constraint for constraint in constraints.values()
        if str(getattr(getattr(constraint, "Expression", None), "Name", "")).lower() == "p3_source"
    ]
    local_p3_constraints = [
        constraint for constraint in constraints.values()
        if str(getattr(getattr(constraint, "Expression", None), "Name", "")).lower() == "p3"
    ]
    if len(source_constraints) == 1:
        inherited = source_constraints[0]
    elif not source_constraints and len(local_p3_constraints) == 1:
        inherited = local_p3_constraints[0]
        local_p3_constraints = []
    else:
        raise RuntimeError("Expected one inherited GBK p3 source")
    expression = inherited.Expression
    if not math.isfinite(float(expression.Value)) or abs(float(expression.Value) - 75.0) > 1e-6:
        raise RuntimeError("The shared jaw strategy requires the recorded p3 source of 75 mm")
    for constraint in local_p3_constraints:
        setup.require_setup_owned(constraint, machine_part)
        constraint.Suppressed = True
    setup.require_setup_owned(inherited, machine_part)
    inherited.Suppressed = False
    session = NXOpen.Session.GetSession()
    session.UpdateManager.DoUpdate(session.NewestVisibleUndoMark)
    print(
        "Flow 4 start hersteld: inherited GBK actief met "
        f"{expression.Name}=75.000000 mm.",
        flush=True,
    )
    return inherited



def _solve_journal_value(session, machine_part, constraint, expression, value):
    """The recorded RHS edit/solve cycle, shared by initial setup and refresh."""
    setup.require_setup_owned(constraint, machine_part)
    setup.require_setup_owned(expression, machine_part)
    positioner, network = setup.begin_network(machine_part, NXOpen)
    try:
        network.AddConstraint(constraint)
        network.IsReferencedGeometryLoaded()
        network.AddConstraint(constraint)
        expression.RightHandSide = f"{value:.9f}"
        network.Solve()
        network.Solve()
        network.AddConstraint(constraint)
        network.Solve()
        network.Solve()
    finally:
        positioner.PrimaryArrangement = None
        positioner.ClearNetwork()
        positioner.EndAssemblyConstraints()
    session.UpdateManager.DoUpdate(session.NewestVisibleUndoMark)


def refresh_jaw_parameter(session, machine_part, diameter, device_root):
    """Edit only the cloned local p3; do not restore or copy inherited constraints."""
    _outer, _chuck, base_jaws = _journal_base_jaw_components(machine_part, device_root)
    matches = {
        constraint.Tag: constraint
        for base_jaw in base_jaws for constraint in base_jaw.GetConstraints()
        if not constraint.Suppressed
        and str(getattr(getattr(constraint, "Expression", None), "Name", "")).lower() == "p3"
        and constraint.OwningPart.Tag == machine_part.Tag
    }
    if len(matches) != 1:
        raise RuntimeError("Refresh requires the single existing setup-local p3 override")
    constraint = next(iter(matches.values()))
    target = 75.0 + (float(diameter) - LOWEST_GRIP_EDGE_DIAMETER) / 2.0
    if not math.isfinite(target) or target <= 0:
        raise ValueError(f"Invalid refreshed jaw opening: {target}")
    _solve_journal_value(session, machine_part, constraint, constraint.Expression, target)
    if str(constraint.GetConstraintStatus()) not in {"0", "9"}:
        raise RuntimeError("The refreshed local jaw constraint did not solve")
    return target, float(diameter) / 2.0


def apply_journal_diameter_parameter(
    session, machine_part, spanning_diameter, device_file, device_root
):
    """Apply the active source's calibrated lowest-edge correction to local p3."""
    _outer, _chuck_assy, base_jaws = _journal_base_jaw_components(machine_part, device_root)

    def expression_value(expression, label):
        rhs = str(expression.RightHandSide)
        match = re.search(r"[-+]?\d+(?:\.\d+)?", rhs)
        if not match:
            raise RuntimeError(f"De {label}-waarde is niet numeriek: {rhs}")
        return float(match.group(0))

    inherited = _restore_p3_start(machine_part, base_jaws)
    original_expression = getattr(inherited, "Expression", None)
    if original_expression is None:
        raise RuntimeError("De bestaande GBK-distanceconstraint heeft geen expressie.")
    original_distance = expression_value(original_expression, "oorspronkelijke p3")

    # Copy the inherited p3 constraint to the local override, then keep the
    # parameter name p3.  NX requires the inherited source to be renamed first
    # because two expressions cannot share the name p3.  No p5 is created.
    copied = None
    for base_jaw in base_jaws:
        for constraint in base_jaw.GetConstraints():
            expression = getattr(constraint, "Expression", None)
            if (
                expression is not None
                and str(getattr(expression, "Name", "")).lower() == "p3"
                and constraint.Tag != inherited.Tag
            ):
                copied = constraint
                break
        if copied is not None:
            break
    if copied is None:
        copied = inherited.CopyInheritedToOverride()
        inherited_expression = getattr(inherited, "Expression", None)
        local_expression = getattr(copied, "Expression", None)
        if inherited_expression is None or local_expression is None:
            raise RuntimeError("De lokale GBK-override heeft geen p3-expressie.")
        if str(getattr(inherited_expression, "Name", "")).lower() == "p3":
            setup.require_setup_owned(inherited_expression, machine_part)
            inherited_expression.SetName("p3_source")
        setup.require_setup_owned(local_expression, machine_part)
        local_expression.SetName("p3")
    setup.require_setup_owned(inherited, machine_part)
    setup.require_setup_owned(copied, machine_part)
    inherited.Suppressed = True
    copied.Suppressed = False
    expression = getattr(copied, "Expression", None)
    if expression is None:
        raise RuntimeError("De lokale GBK-override heeft geen p3-expressie.")
    session.UpdateManager.DoUpdate(session.NewestVisibleUndoMark)

    # This is the recorded journal baseline (p3=75), now applied to the local
    # override rather than attempting to edit the invisible inherited source.
    _solve_journal_value(session, machine_part, copied, expression, original_distance)

    target_radius = float(spanning_diameter) / 2.0
    # User-confirmed lowest gripping edge from the saved output circle/edge
    # measurement.  This is the edge point that must grip the blank; it is
    # not the larger adjacent jaw face selected by the former heuristic.
    start_diameter = LOWEST_GRIP_EDGE_DIAMETER
    start_radius = start_diameter / 2.0
    start_radii = (start_radius, start_radius, start_radius)
    radial_correction = (float(spanning_diameter) - start_diameter) / 2.0
    target_p3 = original_distance + radial_correction
    if target_p3 <= 0:
        raise RuntimeError(f"Berekende p3-waarde is ongeldig: {target_p3:.6f} mm.")

    # Apply the requested radius correction exactly once.  The correction is
    # diameter difference / 2 because the journal distance is radial.
    _solve_journal_value(session, machine_part, copied, expression, target_p3)

    copied_status = str(copied.GetConstraintStatus())
    if copied_status not in {"0", "9"}:
        raise RuntimeError(
            f"De lokale journalconstraint heeft status {copied_status}"
        )
    print(
        "Flow 4 tangentcirkel-parameter: laagste jaw-edge en p3 lokaal "
        "berekend; "
        f"p3={original_distance:.6f} mm; "
        f"startdiameter={start_diameter:.6f} mm; "
        f"start-radii={[round(value, 3) for value in start_radii]} mm; "
        f"radiale-correctie={radial_correction:.6f} mm; "
        f"blank-radius={target_radius:.3f} mm; p3={target_p3:.6f} mm.",
        flush=True,
    )
    return target_p3, target_radius

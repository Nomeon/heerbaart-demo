"""Active workholding builders extracted from Setup_Generator/flow6/flow6_attach_holders.py."""

import NXOpen
import NXOpen.Positioning

from . import common as setup
from .product import _journal_product_touch_constraints
from .product import _product_center_constraints

from .jaws import LOWEST_GRIP_EDGE_DIAMETER


def validate_flow4_reopen(
    machine_part,
    input_file,
    device_file,
    expected_p3,
    expected_radius,
    expect_journal_touch=False,
):
    """Validate the staged Flow4 file after NX has saved and reopened it."""
    root = machine_part.ComponentAssembly.RootComponent
    existing_jaws = [
        component for component in root.GetChildren()
        if component.DisplayName.upper() == device_file.stem.upper()
    ]
    if len(existing_jaws) != 3:
        raise RuntimeError(
            f"Flow 4 reopencontrole vond {len(existing_jaws)} jaws; verwacht exact 3."
        )
    # The full chuck structure is loaded once by main before the final
    # constraint validation.
    _z, _base_assy, base_jaws = setup.find_left_chuck_and_jaws(machine_part)
    active_p3 = []
    active_p5 = []
    for base_jaw in base_jaws:
        for constraint in base_jaw.GetConstraints():
            expression = getattr(constraint, "Expression", None)
            name = str(getattr(expression, "Name", "")).lower()
            if expression is not None and not getattr(constraint, "Suppressed", False):
                if name == "p3":
                    active_p3.append(expression)
                elif name == "p5":
                    active_p5.append(expression)
    if len(active_p3) != 1:
        raise RuntimeError(
            f"Flow 4 reopencontrole vond {len(active_p3)} actieve p3-expressies; verwacht 1."
        )
    if active_p5:
        raise RuntimeError(
            f"Flow 4 reopencontrole vond nog {len(active_p5)} actieve p5-expressies."
        )
    # A referenced library expression named p5 may remain in NX after the
    # obsolete assembly constraint is removed.  Deleting such an expression
    # by name can damage the referenced jaw library.  The safety condition is
    # that no active p5 assembly constraint remains, which was checked above.
    actual_p3 = float(active_p3[0].Value)
    if abs(actual_p3 - expected_p3) > 1e-5:
        raise RuntimeError(
            f"Flow 4 reopencontrole vond p3={actual_p3:.9f}; "
            f"verwacht {expected_p3:.9f}."
        )
    # Do not validate the old adjacent-face heuristic here.  The user-defined
    # grip reference is the lowest jaw-edge measured from the saved circle;
    # the applied journal value is already checked above and the constraint
    # status/conflict scan below validates the NX solve.
    tooth_radii = []
    conflicts = []
    for constraint, owner in setup.snapshot_constraint_baseline(machine_part).values():
        try:
            status = str(constraint.GetConstraintStatus())
        except Exception as error:
            conflicts.append(f"{owner}: status-read-error={error}")
            continue
        if status in {"3", "4", "5", "6", "8", "10", "13", "16", "17", "18"}:
            conflicts.append(f"{owner}: status={status}")
    if conflicts:
        raise RuntimeError("Flow 4 reopencontrole vond conflicts: " + "; ".join(conflicts))
    center_candidates = _product_center_constraints(machine_part, input_file)
    active_center = [
        candidate
        for candidate in center_candidates
        if not candidate.Suppressed
    ]
    if expect_journal_touch:
        active_touch = _journal_product_touch_constraints(machine_part, input_file)
        active_concentric = [
            candidate
            for candidate in active_center
            if candidate.ConstraintType == NXOpen.Positioning.Constraint.Type.Concentric
        ]
        if len(active_touch) != 1 or active_concentric:
            raise RuntimeError(
                "Flow 5 journalcontrole verwacht exact één actieve Touch en "
                f"geen Concentric: {[(item.Tag, item.Name, str(item.ConstraintType)) for item in active_center]}"
            )
    elif active_center:
        raise RuntimeError(
            "Flow 4 centercontrole vond nog een actieve product-centerconstraint: "
            f"{[(item.Tag, item.Name) for item in active_center]}"
        )
    if "FLOW4_CENTER" in " ".join(
        component.DisplayName.upper()
        for component in machine_part.ComponentAssembly.RootComponent.GetChildren()
    ):
        raise RuntimeError(
            "Flow 4 centercontrole vond nog een tijdelijke FLOW4_CENTER-component."
        )
    product_candidates = [
        component
        for component in machine_part.ComponentAssembly.RootComponent.GetChildren()
        if setup.prototype_path(component).stem.casefold() == input_file.stem.casefold()
    ]
    if len(product_candidates) != 1:
        raise RuntimeError(
            "Flow 4 centercontrole vond niet exact één product occurrence: "
            f"{[component.DisplayName for component in product_candidates]}"
        )
    product = product_candidates[0]
    blank_stem = input_file.stem.removesuffix("_ASSY") + "_BLANK"
    blank = setup.find_product_component(product, blank_stem)
    product_point, _matrix = product.GetPosition()
    blank_point, _matrix = blank.GetPosition()
    if (
        abs(float(product_point.X)) > 1e-5
        or abs(float(product_point.Y)) > 1e-5
        or abs(float(blank_point.X)) > 1e-5
        or abs(float(blank_point.Y)) > 1e-5
    ):
        raise RuntimeError(
            "Flow 4 centercontrole: product/blank staan niet op de "
            f"chuck-as: product=({product_point.X}, {product_point.Y}), "
            f"blank=({blank_point.X}, {blank_point.Y})."
        )
    chucks = [
        component
        for component in machine_part.ComponentAssembly.RootComponent.GetChildren()
        if component.DisplayName.upper() == "SMW_KNCS-N_400-128-A8_OUT"
    ]
    if len(chucks) != 2:
        raise RuntimeError(
            "Flow 4 centercontrole vond niet exact twee klauwplaten: "
            f"{len(chucks)}."
        )
    midpoint_z = sum(float(component.GetPosition()[0].Z) for component in chucks) / 2.0
    if not expect_journal_touch and abs(float(product_point.Z) - midpoint_z) > 1e-5:
        raise RuntimeError(
            f"Flow 4 centercontrole: product-Z={product_point.Z:.6f}; "
            f"verwacht midden-Z={midpoint_z:.6f}."
        )
    center_state = (
        "journal Touch actief"
        if expect_journal_touch
        else "geen product-centerconstraint actief"
    )
    print(
        f"Flow 4 reopencontrole OK: 3 jaws, "
        f"laagste-jaw-edge-referentie={LOWEST_GRIP_EDGE_DIAMETER:.6f} mm, "
        f"p3={actual_p3:.6f} mm, product-Z={product_point.Z:.6f}, "
        f"{center_state}, "
        "geen constraint-conflicts.",
        flush=True,
    )

"""Shared expression, point, and HB readback operations from the Elster journals."""

import math

import NXOpen
import NXOpen.Features


def set_attributes(nx_object, values):
    for name, value in values.items():
        nx_object.SetAttribute(name, str(value))


def create_expressions(part, expressions, source="Fixed reviewed Elster Rev.D dimensions"):
    units_mm = part.UnitCollection.FindObject("MilliMeter")
    units_deg = part.UnitCollection.FindObject("Degrees")
    for name, formula, unit in expressions:
        statement = name + " = " + formula
        if unit == "Integer":
            expression = part.Expressions.NewExpression("Integer", statement, None, False, False)
        else:
            expression = part.Expressions.CreateNumberExpression(
                statement, units_deg if unit == "deg" else units_mm
            )
        expression.EditComment(source)


def scalar_expression(work_part, name):
    return work_part.Scalars.CreateScalarExpression(
        work_part.Expressions.FindObject(name),
        NXOpen.Scalar.DimensionalityType.Length,
        NXOpen.SmartObject.UpdateOption.WithinModeling,
    )


def update(label):
    session = NXOpen.Session.GetSession()
    mark = session.SetUndoMark(NXOpen.Session.MarkVisibility.Invisible, label)
    errors = session.UpdateManager.DoUpdate(mark)
    if errors:
        raise RuntimeError(f"{label}: NX reported {errors} update errors")


def solid_body(part):
    bodies = list(part.Bodies)
    if len(bodies) != 1 or not bodies[0].IsSolidBody:
        raise RuntimeError("Elster STAP1-11 requires exactly one solid body")
    return bodies[0]


def save(part):
    update("Save Elster model")
    part.Save(
        NXOpen.BasePart.SaveComponents.TrueValue,
        NXOpen.BasePart.CloseAfterSave.FalseValue,
    ).Dispose()


def reopen(session, part):
    path = part.FullPath
    save(part)
    part.Close(
        NXOpen.BasePart.CloseWholeTree.TrueValue,
        NXOpen.BasePart.CloseModified.CloseModified,
        None,
    )
    reopened, status = session.Parts.OpenBaseDisplay(path)
    try:
        if status.NumberUnloadedParts:
            raise RuntimeError(f"Could not fully reopen Elster model: {path}")
    finally:
        status.Dispose()
    return reopened


def pin_thread(builder, entry):
    # ThreadSize alone can leave generic NX tap-drill, tip, and chamfer defaults.
    builder.RelateHoleDepthToThreadDepth = False
    builder.TapDrillDiameter.SetFormula(str(entry["tap_drill_diameter_mm"]))
    builder.ThreadedTipAngle.SetFormula(str(entry["hole_tip_angle_deg"]))
    for end in ("Start", "End"):
        getattr(builder, "Threaded" + end + "ChamferDiameter").SetFormula(
            str(entry[end.lower() + "_chamfer_diameter_mm"])
        )
        getattr(builder, "Threaded" + end + "ChamferAngle").SetFormula(
            str(entry[end.lower() + "_chamfer_angle_deg"])
        )


def verify_thread(part, feature, entry, thread_depth, drill_depth, *, end_chamfer=False):
    builder = part.Features.CreateHolePackageBuilder(feature)
    try:
        if (
            builder.Type != NXOpen.Features.HolePackageBuilder.Types.ThreadedHole
            or builder.ThreadStandard != entry["standard"]
            or builder.ThreadSize != entry["size"]
            or builder.RadialEngageOption != entry["radial_engage"]
            or not builder.ThreadedStartChamferEnabled
            or bool(builder.ThreadedEndChamferEnabled) != end_chamfer
        ):
            raise RuntimeError(f"{feature.Name}: committed HB thread selection/chamfers differ")
        checks = {
            "ThreadDepth": thread_depth,
            "ThreadedHoleDepth": drill_depth,
            "TapDrillDiameter": entry["tap_drill_diameter_mm"],
            "ThreadedTipAngle": entry["hole_tip_angle_deg"],
            "ThreadedStartChamferDiameter": entry["start_chamfer_diameter_mm"],
            "ThreadedStartChamferAngle": entry["start_chamfer_angle_deg"],
            "ThreadedEndChamferDiameter": entry["end_chamfer_diameter_mm"],
            "ThreadedEndChamferAngle": entry["end_chamfer_angle_deg"],
        }
        for field, expected in checks.items():
            actual = float(getattr(builder, field).Value)
            if not math.isclose(actual, expected, rel_tol=0, abs_tol=0.001):
                raise RuntimeError(f"{feature.Name}: {field} is {actual}, expected {expected}")
    finally:
        builder.Destroy()

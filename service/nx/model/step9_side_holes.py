"""Active builders extracted from elster_family/nx_step9_side_face_holes_journal.py."""

from __future__ import annotations

import NXOpen
import NXOpen.Features
import NXOpen.GeometricUtilities

from .common import scalar_expression, set_attributes, pin_thread

STEP_NAME = "STAP9_SIDE_FACE_HOLES_90_MINUS90"
CAM_RULE_SCHEMA = "ELSTER_CAM_RULES_V1"


def create_point(work_part, position: dict, *, probe: bool):
    formulas = position["probe_formulas"] if probe else position["entry_formulas"]
    point = work_part.Points.CreatePoint(scalar_expression(work_part, formulas["x"]), scalar_expression(work_part, formulas["y"]), scalar_expression(work_part, formulas["z"]), NXOpen.SmartObject.UpdateOption.WithinModeling)
    point.SetName("STAP9_{}_{}POINT".format(position["position_id"], "PROBE_" if probe else "ENTRY_"))
    return point


def create_coordinate_expressions(work_part, positions):
    units = work_part.UnitCollection.FindObject("MilliMeter")
    sources: dict[str, str] = {}
    result = []
    for position in positions:
        coordinates = {}
        for kind in ("entry", "probe"):
            formulas = position[f"{kind}_formulas"]
            mapped = {}
            for axis in ("x", "y", "z"):
                name = "STAP9_COORD_{}_{}_{}_{}".format(position["position_id"], kind.upper(), axis.upper(), "VALUE")
                if name not in sources:
                    work_part.Expressions.CreateNumberExpression(name + " = " + formulas[axis], units)
                    sources[name] = formulas[axis]
                mapped[axis] = name
            coordinates = {**coordinates, kind + "_formulas": mapped}
        result.append({**position, **coordinates})
    return result


def side_inward_direction(work_part, plane_side: str):
    vector = (0.0, -1.0, 0.0) if plane_side == "POS_Y" else (0.0, 1.0, 0.0)
    return work_part.Directions.CreateDirection(NXOpen.Point3d(0.0, 0.0, 0.0), NXOpen.Vector3d(*vector), NXOpen.SmartObject.UpdateOption.WithinModeling)


def create_h9_hole(work_part, body, point, position: dict, contract: dict):
    builder = work_part.Features.CreateHolePackageBuilder(NXOpen.Features.HolePackage.Null)
    try:
        builder.Tolerance = 0.01
        builder.Type = NXOpen.Features.HolePackageBuilder.Types.GeneralHole
        builder.GeneralHoleForm = NXOpen.Features.HolePackageBuilder.HoleForms.Countersink
        builder.GeneralCountersinkHoleDiameter.SetFormula("STEP9_SIDE_H9_DIAMETER")
        builder.GeneralCountersinkDiameter.SetFormula("STEP9_SIDE_H9_CHAMFER_DIAMETER")
        builder.GeneralCountersinkAngle.SetFormula("STEP9_SIDE_H9_CHAMFER_ANGLE")
        builder.HoleDepthLimitOption = NXOpen.Features.HolePackageBuilder.HoleDepthLimitOptions.UntilNext
        builder.DepthOption = NXOpen.Features.HolePackageBuilder.HoleDepthOptions.ToCylinderBottom
        builder.ProjectPointOntoTargetEnabled = True
        builder.ProjectionDirection.ProjectDirectionMethod = NXOpen.GeometricUtilities.ProjectionOptions.DirectionType.Vector
        builder.ProjectionDirection.ProjectVector = side_inward_direction(work_part, position["plane_side"])
        builder.BooleanOperation.Type = NXOpen.GeometricUtilities.BooleanOperation.BooleanType.Subtract
        builder.BooleanOperation.SetTargetBodies([body])
        builder.HolePosition.AddSmartPoint(point, 0.01)
        feature = builder.CommitFeature()
        feature.SetName("STAP9_{}_H9_COUNTERSINK_HOLE".format(position["position_id"]))
        set_attributes(feature, {
            "ELSTER_CAM_RULE_SCHEMA": CAM_RULE_SCHEMA,
            "ELSTER_CAM_FEATURE_ID": "STAP9_{}".format(position["position_id"]),
            "ELSTER_CAM_FEATURE_CLASS": "H9_THROUGH_HOLE_WITH_SPECIAL_CHAMFER",
            "ELSTER_CAM_PROCESS": "H9_THROUGH_HOLEMAKING_WITH_SPECIAL_CHAMFER",
            "ELSTER_CAM_STEP": STEP_NAME,
            "ELSTER_CAM_POSITION_ID": position["position_id"],
            "ELSTER_CAM_FACE_ID": position["face_id"],
            "ELSTER_CAM_HOLE_CALLOUT": "DIAMETER20 H9",
            "ELSTER_CAM_HOLE_DIAMETER_EXPRESSION": "STEP9_SIDE_H9_DIAMETER",
            "ELSTER_CAM_HOLE_DEPTH_LIMIT": "UNTIL_NEXT_LOCAL_WALL",
            "ELSTER_CAM_SPECIAL_CHAMFER_DIAMETER_EXPRESSION": "STEP9_SIDE_H9_CHAMFER_DIAMETER",
            "ELSTER_CAM_SPECIAL_CHAMFER_ANGLE_EXPRESSION": "STEP9_SIDE_H9_CHAMFER_ANGLE",
            "ELSTER_NATIVE_FEATURE_TYPE": "HOLE PACKAGE / GENERAL COUNTERSINK",
            "ELSTER_CAM_ACCESS_VECTOR": position["access_vector"],
        })
        return feature
    finally:
        builder.Destroy()


def create_m8_hole(work_part, body, point, position: dict, contract: dict):
    m8 = contract["side_holes"]["m8"]
    hb = m8["hb_standard"]
    builder = work_part.Features.CreateHolePackageBuilder(NXOpen.Features.HolePackage.Null)
    try:
        builder.Tolerance = 0.01
        builder.Type = NXOpen.Features.HolePackageBuilder.Types.ThreadedHole
        builder.ThreadStandard = hb["standard"]
        builder.ThreadSize = hb["size"]
        builder.RadialEngageOption = hb["radial_engage"]
        pin_thread(builder, hb)
        builder.ThreadLengthOption = NXOpen.Features.HolePackageBuilder.ThreadLengthOptions.Custom
        builder.ThreadDepth.SetFormula("STEP9_SIDE_M8_THREAD_DEPTH")
        builder.ThreadedHoleDepth.SetFormula("STEP9_SIDE_M8_TOTAL_DEPTH")
        builder.ThreadedTipAngle.SetFormula("STEP9_SIDE_M8_HOLE_TIP_ANGLE")
        builder.ThreadedReliefEnabled = False
        builder.ThreadedStartChamferEnabled = True
        builder.ThreadedStartChamferDiameter.SetFormula("STEP9_SIDE_M8_START_CHAMFER_DIAMETER")
        builder.ThreadedStartChamferAngle.SetFormula("STEP9_SIDE_M8_START_CHAMFER_ANGLE")
        builder.ThreadedEndChamferEnabled = False
        builder.HoleDepthLimitOption = NXOpen.Features.HolePackageBuilder.HoleDepthLimitOptions.Value
        builder.DepthOption = NXOpen.Features.HolePackageBuilder.HoleDepthOptions.ToConeTip
        builder.ThreadRotation = NXOpen.Features.HolePackageBuilder.ThreadRotationOptions.Right
        builder.ThreadAtBothEnds = False
        builder.ProjectPointOntoTargetEnabled = False
        builder.ProjectionDirection.ProjectDirectionMethod = NXOpen.GeometricUtilities.ProjectionOptions.DirectionType.Vector
        builder.ProjectionDirection.ProjectVector = side_inward_direction(work_part, position["plane_side"])
        builder.BooleanOperation.Type = NXOpen.GeometricUtilities.BooleanOperation.BooleanType.Subtract
        builder.BooleanOperation.SetTargetBodies([body])
        builder.HolePosition.AddSmartPoint(point, 0.01)
        feature = builder.CommitFeature()
        feature.SetName("STAP9_{}_M8_THREADED_HOLE".format(position["position_id"]))
        set_attributes(feature, {
            "ELSTER_CAM_RULE_SCHEMA": CAM_RULE_SCHEMA,
            "ELSTER_CAM_FEATURE_ID": "STAP9_{}".format(position["position_id"]),
            "ELSTER_CAM_FEATURE_CLASS": "METRIC_M8_BLIND_THREAD_ON_90_DEGREE_FLAT",
            "ELSTER_CAM_PROCESS": "M8_THREAD_HOLEMAKING",
            "ELSTER_CAM_STEP": STEP_NAME,
            "ELSTER_CAM_POSITION_ID": position["position_id"],
            "ELSTER_CAM_FACE_ID": position["face_id"],
            "ELSTER_NATIVE_FEATURE_TYPE": "HOLE PACKAGE / THREADED HOLE",
            "ELSTER_CAM_THREAD_CALLOUT": "M8 x 1.25",
            "ELSTER_CAM_THREAD_STANDARD": hb["standard"],
            "ELSTER_CAM_THREAD_SIZE": hb["size"],
            "ELSTER_CAM_THREAD_DEPTH_EXPRESSION": "STEP9_SIDE_M8_THREAD_DEPTH",
            "ELSTER_CAM_TOTAL_DEPTH_EXPRESSION": "STEP9_SIDE_M8_TOTAL_DEPTH",
            "ELSTER_CAM_START_CHAMFER_DIAMETER_EXPRESSION": "STEP9_SIDE_M8_START_CHAMFER_DIAMETER",
            "ELSTER_CAM_START_CHAMFER_ANGLE_EXPRESSION": "STEP9_SIDE_M8_START_CHAMFER_ANGLE",
            "ELSTER_CAM_ACCESS_VECTOR": position["access_vector"],
            "ELSTER_CAM_HB_TABLE_SHA256": hb["table_sha256"],
        })
        return feature
    finally:
        builder.Destroy()

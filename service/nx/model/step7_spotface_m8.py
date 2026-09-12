"""Active builders extracted from elster_family/nx_step7_m8_16x_journal.py."""

from __future__ import annotations

import NXOpen
import NXOpen.Features
import NXOpen.GeometricUtilities

from .common import scalar_expression, set_attributes

STEP_NAME = "STAP7_HB_M8_16X"
CAM_RULE_SCHEMA = "ELSTER_CAM_RULES_V1"


def create_probe_point(work_part, position: dict):
    point = work_part.Points.CreatePoint(
        scalar_expression(work_part, position["x_expression"]),
        scalar_expression(work_part, position["y_expression"]),
        scalar_expression(work_part, position["probe_z_expression"]),
        NXOpen.SmartObject.UpdateOption.WithinModeling,
    )
    point.SetName("STAP7_{}_PROBE_POINT".format(position["position_id"]))
    return point


def create_entry_point(work_part, position: dict):
    point = work_part.Points.CreatePoint(
        scalar_expression(work_part, position["x_expression"]),
        scalar_expression(work_part, position["y_expression"]),
        scalar_expression(work_part, position["entry_z_expression"]),
        NXOpen.SmartObject.UpdateOption.WithinModeling,
    )
    point.SetName("STAP7_{}_ENTRY_POINT".format(position["position_id"]))
    return point


def inward_z_direction(work_part, side: str):
    vector = (0.0, 0.0, -1.0) if side == "Z_POS" else (0.0, 0.0, 1.0)
    return work_part.Directions.CreateDirection(
        NXOpen.Point3d(0.0, 0.0, 0.0),
        NXOpen.Vector3d(*vector),
        NXOpen.SmartObject.UpdateOption.WithinModeling,
    )


def create_spotface(work_part, body, point, position: dict, contract: dict):
    builder = work_part.Features.CreateHolePackageBuilder(NXOpen.Features.HolePackage.Null)
    try:
        builder.Tolerance = 0.01
        builder.Type = NXOpen.Features.HolePackageBuilder.Types.GeneralHole
        builder.GeneralHoleForm = NXOpen.Features.HolePackageBuilder.HoleForms.Simple
        builder.GeneralSimpleHoleDiameter.SetFormula("STEP7_M8_SPOTFACE_DIAMETER")
        builder.GeneralSimpleHoleDepth.SetFormula("STEP7_M8_SPOTFACE_DEPTH")
        builder.HoleDepthLimitOption = NXOpen.Features.HolePackageBuilder.HoleDepthLimitOptions.Value
        builder.DepthOption = NXOpen.Features.HolePackageBuilder.HoleDepthOptions.ToCylinderBottom
        builder.ProjectPointOntoTargetEnabled = True
        builder.ProjectionDirection.ProjectDirectionMethod = NXOpen.GeometricUtilities.ProjectionOptions.DirectionType.Vector
        builder.ProjectionDirection.ProjectVector = inward_z_direction(work_part, position["side"])
        builder.BooleanOperation.Type = NXOpen.GeometricUtilities.BooleanOperation.BooleanType.Subtract
        builder.BooleanOperation.SetTargetBodies([body])
        builder.HolePosition.AddSmartPoint(point, 0.01)
        feature = builder.CommitFeature()
        feature_expressions = feature.GetExpressions()
        if len(feature_expressions) < 3:
            raise RuntimeError("De native simple Hole Package heeft geen bodemhoek-expression.")
        # NX creates the third native simple-hole expression as the drill-tip
        # angle (118 degrees by default). Bind it to the contract expression
        # so the D15 spotface is a true flat-bottom Hole feature at 0 degrees.
        feature_expressions[2].SetFormula("STEP7_M8_SPOTFACE_BOTTOM_ANGLE")
        feature.SetName("STAP7_{}_D15_SPOTFACE".format(position["position_id"]))
        set_attributes(feature, {
            "ELSTER_CAM_RULE_SCHEMA": CAM_RULE_SCHEMA,
            "ELSTER_CAM_FEATURE_ID": "STAP7_{}_SPOTFACE".format(position["position_id"]),
            "ELSTER_CAM_FEATURE_CLASS": "LOCAL_D15_SPOTFACE",
            "ELSTER_CAM_PROCESS": "SPOTFACE_HOLEMAKING",
            "ELSTER_CAM_STEP": STEP_NAME,
            "ELSTER_CAM_POSITION_ID": position["position_id"],
            "ELSTER_CAM_SIDE": position["side"],
            "ELSTER_NATIVE_FEATURE_TYPE": "HOLE PACKAGE / SIMPLE HOLE / 0 DEG FLAT BOTTOM",
            "ELSTER_CAM_SPOTFACE_DIAMETER_EXPRESSION": "STEP7_M8_SPOTFACE_DIAMETER",
            "ELSTER_CAM_SPOTFACE_DEPTH_EXPRESSION": "STEP7_M8_SPOTFACE_DEPTH",
            "ELSTER_CAM_SPOTFACE_BOTTOM_ANGLE_EXPRESSION": "STEP7_M8_SPOTFACE_BOTTOM_ANGLE",
            "ELSTER_CAM_ACCESS_VECTOR": position["access_vector"],
        })
        return feature
    finally:
        builder.Destroy()


def create_m8_hole(work_part, body, point, position: dict, contract: dict):
    plan = contract["m8_holes"]
    hb = plan["hb_standard"]
    builder = work_part.Features.CreateHolePackageBuilder(NXOpen.Features.HolePackage.Null)
    try:
        builder.Tolerance = 0.01
        builder.Type = NXOpen.Features.HolePackageBuilder.Types.ThreadedHole
        builder.ThreadStandard = hb["standard"]
        builder.ThreadSize = hb["size"]
        builder.RadialEngageOption = hb["radial_engage"]
        builder.ThreadLengthOption = NXOpen.Features.HolePackageBuilder.ThreadLengthOptions.Custom
        builder.ThreadDepth.SetFormula("STEP7_M8_THREAD_DEPTH")
        builder.ThreadedHoleDepth.SetFormula("STEP7_M8_TOTAL_DEPTH")
        builder.ThreadedTipAngle.SetFormula("STEP7_M8_HOLE_TIP_ANGLE")

        # The local diameter-15 spotface is a preceding native blind simple
        # Hole Package. It leaves a single D15 entry with a solid reference
        # at the bottom; the M8 feature starts from its expression-driven
        # entry point. ThreadedRelief remains disabled so NX retains the
        # explicit ThreadedStartChamfer.
        builder.ThreadedReliefEnabled = False
        builder.ThreadedStartChamferEnabled = True
        builder.ThreadedStartChamferDiameter.SetFormula("STEP7_M8_START_CHAMFER_DIAMETER")
        builder.ThreadedStartChamferAngle.SetFormula("STEP7_M8_START_CHAMFER_ANGLE")
        builder.ThreadedEndChamferEnabled = False
        builder.HoleDepthLimitOption = NXOpen.Features.HolePackageBuilder.HoleDepthLimitOptions.Value
        builder.DepthOption = NXOpen.Features.HolePackageBuilder.HoleDepthOptions.ToConeTip
        builder.ThreadRotation = NXOpen.Features.HolePackageBuilder.ThreadRotationOptions.Right
        builder.ThreadAtBothEnds = False
        builder.ProjectPointOntoTargetEnabled = False
        builder.ProjectionDirection.ProjectDirectionMethod = NXOpen.GeometricUtilities.ProjectionOptions.DirectionType.Vector
        builder.ProjectionDirection.ProjectVector = inward_z_direction(work_part, position["side"])
        builder.BooleanOperation.Type = NXOpen.GeometricUtilities.BooleanOperation.BooleanType.Subtract
        builder.BooleanOperation.SetTargetBodies([body])
        builder.HolePosition.AddSmartPoint(point, 0.01)
        feature = builder.CommitFeature()
        feature.SetName("STAP7_{}_M8_THREADED_HOLE".format(position["position_id"]))
        set_attributes(feature, {
            "ELSTER_CAM_RULE_SCHEMA": CAM_RULE_SCHEMA,
            "ELSTER_CAM_FEATURE_ID": "STAP7_{}".format(position["position_id"]),
            "ELSTER_CAM_FEATURE_CLASS": "METRIC_M8_BLIND_THREAD_WITH_D15_SPOTFACE",
            "ELSTER_CAM_PROCESS": "M8_THREAD_HOLEMAKING_WITH_SPOTFACE",
            "ELSTER_CAM_STEP": STEP_NAME,
            "ELSTER_CAM_POSITION_ID": position["position_id"],
            "ELSTER_CAM_SIDE": position["side"],
            "ELSTER_NATIVE_FEATURE_TYPE": "HOLE PACKAGE / THREADED HOLE",
            "ELSTER_CAM_THREAD_CALLOUT": "M8 x 1.25",
            "ELSTER_CAM_THREAD_STANDARD": hb["standard"],
            "ELSTER_CAM_THREAD_SIZE": hb["size"],
            "ELSTER_CAM_THREAD_DEPTH_EXPRESSION": "STEP7_M8_THREAD_DEPTH",
            "ELSTER_CAM_TOTAL_DEPTH_EXPRESSION": "STEP7_M8_TOTAL_DEPTH",
            "ELSTER_CAM_SPOTFACE_FEATURE": "STAP7_{}_D15_SPOTFACE".format(position["position_id"]),
            "ELSTER_CAM_SPOTFACE_DIAMETER_EXPRESSION": "STEP7_M8_SPOTFACE_DIAMETER",
            "ELSTER_CAM_SPOTFACE_DEPTH_EXPRESSION": "STEP7_M8_SPOTFACE_DEPTH",
            "ELSTER_CAM_START_CHAMFER_DIAMETER_EXPRESSION": "STEP7_M8_START_CHAMFER_DIAMETER",
            "ELSTER_CAM_START_CHAMFER_ANGLE_EXPRESSION": "STEP7_M8_START_CHAMFER_ANGLE",
            "ELSTER_CAM_ACCESS_VECTOR": position["access_vector"],
            "ELSTER_CAM_HB_TABLE_SHA256": hb["table_sha256"],
        })
        return feature
    finally:
        builder.Destroy()

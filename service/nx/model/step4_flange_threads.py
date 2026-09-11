"""Active builders extracted from elster_family/nx_step4_flange_thread_holes_journal.py."""

from __future__ import annotations

import math

import NXOpen
import NXOpen.Features
import NXOpen.GeometricUtilities

from .common import scalar_expression, set_attributes, pin_thread

STEP_NAME = "STAP4_FLANGE_THREAD_HOLES"
CAM_RULE_SCHEMA = "ELSTER_CAM_RULES_V1"


def create_seed_point(work_part, side: str, position: dict):
    x_name = "STEP4_LEFT_FLANGE_CENTER_X" if side == "LEFT" else "STEP4_RIGHT_FLANGE_CENTER_X"
    point = work_part.Points.CreatePoint(
        scalar_expression(work_part, x_name),
        scalar_expression(work_part, position["y_expression"]),
        scalar_expression(work_part, position["z_expression"]),
        NXOpen.SmartObject.UpdateOption.WithinModeling,
    )
    point.SetName(side + "_STAP4_M12_THREAD_" + position["position_id"] + "_POINT")
    return point


def create_threaded_hole(work_part, body, side: str, position: dict, contract: dict):
    plan = contract["radial_thread_holes"]
    hb = plan["hb_standard"]
    point = create_seed_point(work_part, side, position)
    builder = work_part.Features.CreateHolePackageBuilder(NXOpen.Features.HolePackage.Null)
    try:
        builder.Tolerance = 0.01
        builder.Type = NXOpen.Features.HolePackageBuilder.Types.ThreadedHole
        builder.ThreadStandard = hb["standard"]
        builder.ThreadSize = hb["size"]
        builder.RadialEngageOption = hb["radial_engage"]
        pin_thread(builder, hb)
        builder.ThreadLengthOption = NXOpen.Features.HolePackageBuilder.ThreadLengthOptions.Custom
        builder.ThreadDepth.SetFormula("STEP4_THREAD_DEPTH")
        builder.ThreadedHoleDepth.SetFormula("STEP4_DRILL_DEPTH")
        builder.TapDrillDiameter.SetFormula("STEP4_THREAD_TAP_DRILL_DIAMETER")
        builder.ThreadedTipAngle.SetFormula("STEP4_THREAD_TIP_ANGLE")
        builder.HoleDepthLimitOption = NXOpen.Features.HolePackageBuilder.HoleDepthLimitOptions.Value
        builder.DepthOption = NXOpen.Features.HolePackageBuilder.HoleDepthOptions.ToConeTip
        builder.ThreadRotation = NXOpen.Features.HolePackageBuilder.ThreadRotationOptions.Right
        builder.ThreadAtBothEnds = False
        builder.RelateHoleDepthToThreadDepth = False
        builder.ThreadedStartChamferEnabled = True
        builder.ThreadedStartChamferDiameter.SetFormula("STEP4_THREAD_CHAMFER_DIAMETER")
        builder.ThreadedStartChamferAngle.SetFormula("STEP4_THREAD_CHAMFER_ANGLE")
        builder.ThreadedEndChamferEnabled = True
        builder.ThreadedEndChamferDiameter.SetFormula("STEP4_THREAD_CHAMFER_DIAMETER")
        builder.ThreadedEndChamferAngle.SetFormula("STEP4_THREAD_CHAMFER_ANGLE")
        builder.ProjectPointOntoTargetEnabled = False
        angle_rad = math.radians(float(position["angle_deg"]))
        # STAP4 drawing convention: 0 degrees is the +Z radial datum and
        # positive angles rotate from +Z toward +Y.
        direction = work_part.Directions.CreateDirection(
            NXOpen.Point3d(0.0, 0.0, 0.0),
            NXOpen.Vector3d(0.0, -math.sin(angle_rad), -math.cos(angle_rad)),
            NXOpen.SmartObject.UpdateOption.WithinModeling,
        )
        builder.ProjectionDirection.ProjectDirectionMethod = NXOpen.GeometricUtilities.ProjectionOptions.DirectionType.Vector
        builder.ProjectionDirection.ProjectVector = direction
        builder.BooleanOperation.Type = NXOpen.GeometricUtilities.BooleanOperation.BooleanType.Subtract
        builder.BooleanOperation.SetTargetBodies([body])
        builder.HolePosition.AddSmartPoint(point, 0.01)
        feature = builder.CommitFeature()
        feature.SetName(side + "_STAP4_M12_THREADED_HOLE_" + position["position_id"])
        set_attributes(feature, {
            "ELSTER_CAM_RULE_SCHEMA": CAM_RULE_SCHEMA,
            "ELSTER_CAM_FEATURE_ID": "STAP4_{}_M12_THREAD_{}".format(side, position["position_id"]),
            "ELSTER_CAM_FEATURE_CLASS": "RADIAL_BLIND_THREADED_HOLE",
            "ELSTER_CAM_PROCESS": "RADIAL_THREAD_HOLEMAKING",
            "ELSTER_CAM_STEP": STEP_NAME,
            "ELSTER_CAM_SIDE": side,
            "ELSTER_NATIVE_FEATURE_TYPE": "HOLE PACKAGE",
            "ELSTER_CAM_THREAD_CALLOUT": plan["thread_callout"],
            "ELSTER_CAM_THREAD_STANDARD": hb["standard"],
            "ELSTER_CAM_THREAD_SIZE": hb["size"],
            "ELSTER_CAM_THREAD_DEPTH_EXPRESSION": "STEP4_THREAD_DEPTH",
            "ELSTER_CAM_DRILL_DEPTH_EXPRESSION": "STEP4_DRILL_DEPTH",
            "ELSTER_CAM_ANGLE_EXPRESSION": position["angle_expression"],
            "ELSTER_CAM_Y_EXPRESSION": position["y_expression"],
            "ELSTER_CAM_Z_EXPRESSION": position["z_expression"],
            "ELSTER_CAM_ACCESS_VECTOR": "RADIAL_INWARD_TO_GLOBAL_X_AXIS",
            "ELSTER_CAM_HB_TABLE_SHA256": hb["table_sha256"],
        })
        return feature
    finally:
        builder.Destroy()

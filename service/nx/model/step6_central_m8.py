"""Active builders extracted from elster_family/nx_step6_m8_holes_journal.py."""

from __future__ import annotations

import NXOpen
import NXOpen.Features
import NXOpen.GeometricUtilities

from .common import scalar_expression, set_attributes, pin_thread

STEP_NAME = "STAP6_HB_M8_HOLES"
CAM_RULE_SCHEMA = "ELSTER_CAM_RULES_V1"


def create_m8_point(work_part, position: dict):
    point = work_part.Points.CreatePoint(
        scalar_expression(work_part, position["x_expression"]),
        scalar_expression(work_part, position["y_expression"]),
        scalar_expression(work_part, position["z_expression"]),
        NXOpen.SmartObject.UpdateOption.WithinModeling,
    )
    point.SetName("STAP6_{}_POINT".format(position["position_id"]))
    return point


def inward_z_direction(work_part):
    return work_part.Directions.CreateDirection(
        NXOpen.Point3d(0.0, 0.0, 0.0),
        NXOpen.Vector3d(0.0, 0.0, -1.0),
        NXOpen.SmartObject.UpdateOption.WithinModeling,
    )


def create_m8_hole(work_part, body, position: dict, contract: dict):
    plan = contract["m8_holes"]
    hb = plan["hb_standard"]
    point = create_m8_point(work_part, position)
    builder = work_part.Features.CreateHolePackageBuilder(NXOpen.Features.HolePackage.Null)
    try:
        builder.Tolerance = 0.01
        builder.Type = NXOpen.Features.HolePackageBuilder.Types.ThreadedHole
        builder.ThreadStandard = hb["standard"]
        builder.ThreadSize = hb["size"]
        builder.RadialEngageOption = hb["radial_engage"]
        pin_thread(builder, hb)
        builder.ThreadLengthOption = NXOpen.Features.HolePackageBuilder.ThreadLengthOptions.Custom
        builder.ThreadDepth.SetFormula("STEP6_M8_THREAD_DEPTH")
        builder.ThreadedHoleDepth.SetFormula("STEP6_M8_TOTAL_DEPTH")
        builder.ThreadedTipAngle.SetFormula("STEP6_M8_HOLE_TIP_ANGLE")
        builder.ThreadedStartChamferEnabled = True
        builder.ThreadedStartChamferDiameter.SetFormula("STEP6_M8_START_CHAMFER_DIAMETER")
        builder.ThreadedStartChamferAngle.SetFormula("STEP6_M8_START_CHAMFER_ANGLE")
        # This is a blind hole.  The drawing does not show a through-thread;
        # therefore the explicit end-chamfer rule does not apply here.
        builder.ThreadedEndChamferEnabled = False
        builder.HoleDepthLimitOption = NXOpen.Features.HolePackageBuilder.HoleDepthLimitOptions.Value
        builder.DepthOption = NXOpen.Features.HolePackageBuilder.HoleDepthOptions.ToConeTip
        builder.ThreadRotation = NXOpen.Features.HolePackageBuilder.ThreadRotationOptions.Right
        builder.ThreadAtBothEnds = False
        builder.ProjectPointOntoTargetEnabled = False
        builder.ProjectionDirection.ProjectDirectionMethod = NXOpen.GeometricUtilities.ProjectionOptions.DirectionType.Vector
        builder.ProjectionDirection.ProjectVector = inward_z_direction(work_part)
        builder.BooleanOperation.Type = NXOpen.GeometricUtilities.BooleanOperation.BooleanType.Subtract
        builder.BooleanOperation.SetTargetBodies([body])
        builder.HolePosition.AddSmartPoint(point, 0.01)
        feature = builder.CommitFeature()
        feature.SetName("STAP6_{}_M8_THREADED_HOLE".format(position["position_id"]))
        set_attributes(feature, {
            "ELSTER_CAM_RULE_SCHEMA": CAM_RULE_SCHEMA,
            "ELSTER_CAM_FEATURE_ID": "STAP6_{}_M8".format(position["position_id"]),
            "ELSTER_CAM_FEATURE_CLASS": "METRIC_M8_BLIND_THREAD",
            "ELSTER_CAM_PROCESS": "M8_THREAD_HOLEMAKING",
            "ELSTER_CAM_STEP": STEP_NAME,
            "ELSTER_CAM_POSITION_ID": position["position_id"],
            "ELSTER_NATIVE_FEATURE_TYPE": "HOLE PACKAGE",
            "ELSTER_CAM_THREAD_CALLOUT": "M8 x 1.25",
            "ELSTER_CAM_THREAD_STANDARD": hb["standard"],
            "ELSTER_CAM_THREAD_SIZE": hb["size"],
            "ELSTER_CAM_THREAD_DEPTH_EXPRESSION": "STEP6_M8_THREAD_DEPTH",
            "ELSTER_CAM_TOTAL_DEPTH_EXPRESSION": "STEP6_M8_TOTAL_DEPTH",
            "ELSTER_CAM_START_CHAMFER_DIAMETER_EXPRESSION": "STEP6_M8_START_CHAMFER_DIAMETER",
            "ELSTER_CAM_START_CHAMFER_ANGLE_EXPRESSION": "STEP6_M8_START_CHAMFER_ANGLE",
            "ELSTER_CAM_ACCESS_VECTOR": "RADIAL_INWARD_TO_GLOBAL_MINUS_Z",
            "ELSTER_CAM_HB_TABLE_SHA256": hb["table_sha256"],
        })
        return feature, point
    finally:
        builder.Destroy()

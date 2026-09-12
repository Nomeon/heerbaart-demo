"""Active builders extracted from elster_family/nx_step5_npt_holes_journal.py."""

from __future__ import annotations

import NXOpen
import NXOpen.Features
import NXOpen.GeometricUtilities

from .common import scalar_expression, set_attributes

STEP_NAME = "STAP5_NPT_HOLES"
CAM_RULE_SCHEMA = "ELSTER_CAM_RULES_V1"


def create_port_point(work_part, position: dict):
    point = work_part.Points.CreatePoint(
        scalar_expression(work_part, position["x_expression"]),
        scalar_expression(work_part, position["y_expression"]),
        scalar_expression(work_part, position["z_expression"]),
        NXOpen.SmartObject.UpdateOption.WithinModeling,
    )
    point.SetName("STAP5_{}_PORT_POINT".format(position["position_id"]))
    return point


def inward_z_direction(work_part):
    return work_part.Directions.CreateDirection(
        NXOpen.Point3d(0.0, 0.0, 0.0),
        NXOpen.Vector3d(0.0, 0.0, -1.0),
        NXOpen.SmartObject.UpdateOption.WithinModeling,
    )


def create_npt_hole(work_part, body, position: dict, contract: dict):
    plan = contract["npt_holes"]
    hb = plan["hb_standard"]
    point = create_port_point(work_part, position)
    builder = work_part.Features.CreateHolePackageBuilder(NXOpen.Features.HolePackage.Null)
    try:
        builder.Tolerance = 0.01
        builder.Type = NXOpen.Features.HolePackageBuilder.Types.ThreadedHole
        builder.ThreadStandard = hb["standard"]
        builder.ThreadSize = hb["size"]
        builder.RadialEngageOption = hb["radial_engage"]
        builder.ThreadLengthOption = NXOpen.Features.HolePackageBuilder.ThreadLengthOptions.Custom
        builder.ThreadDepth.SetFormula("STEP5_NPT_THREAD_DEPTH")
        builder.ThreadedHoleDepth.SetFormula("STEP5_NPT_TOTAL_DEPTH")
        builder.ThreadedStartChamferEnabled = True
        builder.ThreadedStartChamferDiameter.SetFormula("STEP5_NPT_START_CHAMFER_DIAMETER")
        builder.ThreadedStartChamferAngle.SetFormula("STEP5_NPT_START_CHAMFER_ANGLE")
        # The NPT feature transitions into the separate coaxial Ø4 feature;
        # an end chamfer would incorrectly enlarge that internal transition.
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
        feature.SetName("STAP5_{}_NPT_THREADED_HOLE".format(position["position_id"]))
        set_attributes(feature, {
            "ELSTER_CAM_RULE_SCHEMA": CAM_RULE_SCHEMA,
            "ELSTER_CAM_FEATURE_ID": "STAP5_{}_NPT".format(position["position_id"]),
            "ELSTER_CAM_FEATURE_CLASS": "TAPERED_NPT_BLIND_THREAD",
            "ELSTER_CAM_PROCESS": "NPT_THREAD_HOLEMAKING",
            "ELSTER_CAM_STEP": STEP_NAME,
            "ELSTER_CAM_POSITION_ID": position["position_id"],
            "ELSTER_NATIVE_FEATURE_TYPE": "HOLE PACKAGE",
            "ELSTER_CAM_THREAD_CALLOUT": npt_callout(hb),
            "ELSTER_CAM_THREAD_STANDARD": hb["standard"],
            "ELSTER_CAM_THREAD_SIZE": hb["size"],
            "ELSTER_CAM_THREAD_DEPTH_EXPRESSION": "STEP5_NPT_THREAD_DEPTH",
            "ELSTER_CAM_TOTAL_DEPTH_EXPRESSION": "STEP5_NPT_TOTAL_DEPTH",
            "ELSTER_CAM_ACCESS_VECTOR": "RADIAL_INWARD_TO_GLOBAL_MINUS_Z",
            "ELSTER_CAM_HB_TABLE_SHA256": hb["table_sha256"],
        })
        return feature
    finally:
        builder.Destroy()


def npt_callout(hb: dict) -> str:
    return hb.get("callout", "1/2-14_NPT")


def create_continuous_hole(work_part, body, position: dict, contract: dict):
    point = create_port_point(work_part, position)
    builder = work_part.Features.CreateHolePackageBuilder(NXOpen.Features.HolePackage.Null)
    try:
        builder.Type = NXOpen.Features.HolePackageBuilder.Types.GeneralHole
        builder.Tolerance = 0.01
        builder.HoleSize = NXOpen.Features.HolePackageBuilder.Holesize.Custom
        builder.GeneralHoleForm = NXOpen.Features.HolePackageBuilder.HoleForms.Simple
        builder.HoleDepthLimitOption = NXOpen.Features.HolePackageBuilder.HoleDepthLimitOptions.Value
        builder.DepthOption = NXOpen.Features.HolePackageBuilder.HoleDepthOptions.ToCylinderBottom
        builder.GeneralSimpleHoleDiameter.SetFormula("STEP5_THROUGH_DIAMETER")
        builder.GeneralSimpleHoleDepth.SetFormula("STEP5_THROUGH_DEPTH")
        builder.ProjectPointOntoTargetEnabled = False
        builder.ProjectionDirection.ProjectDirectionMethod = NXOpen.GeometricUtilities.ProjectionOptions.DirectionType.Vector
        builder.ProjectionDirection.ProjectVector = inward_z_direction(work_part)
        builder.BooleanOperation.Type = NXOpen.GeometricUtilities.BooleanOperation.BooleanType.Subtract
        builder.BooleanOperation.SetTargetBodies([body])
        builder.HolePosition.AddSmartPoint(point, 0.01)
        feature = builder.CommitFeature()
        feature.SetName("STAP5_{}_D4_CONTINUOUS_HOLE".format(position["position_id"]))
        set_attributes(feature, {
            "ELSTER_CAM_RULE_SCHEMA": CAM_RULE_SCHEMA,
            "ELSTER_CAM_FEATURE_ID": "STAP5_{}_D4_CONTINUATION".format(position["position_id"]),
            "ELSTER_CAM_FEATURE_CLASS": "DIAMETER_4_CONTINUOUS_HOLE",
            "ELSTER_CAM_PROCESS": "PILOT_THROUGH_HOLEMAKING",
            "ELSTER_CAM_STEP": STEP_NAME,
            "ELSTER_CAM_POSITION_ID": position["position_id"],
            "ELSTER_NATIVE_FEATURE_TYPE": "HOLE PACKAGE",
            "ELSTER_CAM_DIAMETER_EXPRESSION": "STEP5_THROUGH_DIAMETER",
            "ELSTER_CAM_DEPTH_EXPRESSION": "STEP5_THROUGH_DEPTH",
            "ELSTER_CAM_ACCESS_VECTOR": "RADIAL_INWARD_TO_GLOBAL_MINUS_Z",
        })
        return feature
    finally:
        builder.Destroy()

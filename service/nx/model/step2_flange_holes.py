"""Active builders extracted from elster_family/nx_step2_flange_holes_journal.py."""

from __future__ import annotations

import math

import NXOpen
import NXOpen.Features
import NXOpen.GeometricUtilities
import NXOpen.UF

from .common import scalar_expression, set_attributes

STEP_NAME = "STAP2_FLANGE_HOLES"
CAM_RULE_SCHEMA = "ELSTER_CAM_RULES_V1"


def create_seed_point(work_part, side: str):
    x_name = "STEP2_LEFT_SEED_X" if side == "LEFT" else "STEP2_RIGHT_SEED_X"
    point = work_part.Points.CreatePoint(
        scalar_expression(work_part, x_name),
        scalar_expression(work_part, "STEP2_SEED_Y"),
        scalar_expression(work_part, "STEP2_SEED_Z"),
        NXOpen.SmartObject.UpdateOption.WithinModeling,
    )
    point.SetName(side + "_STAP2_FLANGE_HOLE_SEED_POINT")
    return point


def create_general_hole(work_part, body, side: str):
    point = create_seed_point(work_part, side)
    builder = work_part.Features.CreateHolePackageBuilder(NXOpen.Features.HolePackage.Null)
    try:
        builder.Type = NXOpen.Features.HolePackageBuilder.Types.GeneralHole
        builder.Tolerance = 0.01
        builder.HoleSize = NXOpen.Features.HolePackageBuilder.Holesize.Custom
        builder.GeneralHoleForm = NXOpen.Features.HolePackageBuilder.HoleForms.Simple
        builder.HoleDepthLimitOption = NXOpen.Features.HolePackageBuilder.HoleDepthLimitOptions.Value
        builder.DepthOption = NXOpen.Features.HolePackageBuilder.HoleDepthOptions.ToCylinderBottom
        builder.GeneralSimpleHoleDiameter.SetFormula("DS")
        builder.GeneralSimpleHoleDepth.SetFormula("STEP2_HOLE_DEPTH")
        builder.CustomStartChamferEnabled = True
        builder.CustomStartChamferOffset.SetFormula("STEP2_EDGE_BREAK")
        builder.CustomStartChamferAngle.SetFormula("STEP2_EDGE_BREAK_ANGLE")
        builder.CustomEndChamferEnabled = True
        builder.CustomEndChamferOffset.SetFormula("STEP2_EDGE_BREAK")
        builder.CustomEndChamferAngle.SetFormula("STEP2_EDGE_BREAK_ANGLE")
        builder.ProjectPointOntoTargetEnabled = False
        direction_sign = 1.0 if side == "LEFT" else -1.0
        direction = work_part.Directions.CreateDirection(
            NXOpen.Point3d(0.0, 0.0, 0.0),
            NXOpen.Vector3d(direction_sign, 0.0, 0.0),
            NXOpen.SmartObject.UpdateOption.WithinModeling,
        )
        builder.ProjectionDirection.ProjectDirectionMethod = NXOpen.GeometricUtilities.ProjectionOptions.DirectionType.Vector
        builder.ProjectionDirection.ProjectVector = direction
        builder.BooleanOperation.Type = NXOpen.GeometricUtilities.BooleanOperation.BooleanType.Subtract
        builder.BooleanOperation.SetTargetBodies([body])
        builder.HolePosition.AddSmartPoint(point, 0.01)
        feature = builder.CommitFeature()
        feature.SetName(side + "_STAP2_FLANGE_GENERAL_HOLE")
        set_attributes(feature, {
            "ELSTER_CAM_RULE_SCHEMA": CAM_RULE_SCHEMA,
            "ELSTER_CAM_FEATURE_ID": "STAP2_{}_FLANGE_HOLE_SEED".format(side),
            "ELSTER_CAM_FEATURE_CLASS": "SIMPLE_THROUGH_HOLE",
            "ELSTER_CAM_PROCESS": "AXIAL_FLANGE_HOLEMAKING",
            "ELSTER_CAM_STEP": STEP_NAME,
            "ELSTER_CAM_SIDE": side,
            "ELSTER_NATIVE_FEATURE_TYPE": "HOLE PACKAGE",
            "ELSTER_CAM_DIAMETER_EXPRESSION": "DS",
            "ELSTER_CAM_DEPTH_EXPRESSION": "STEP2_HOLE_DEPTH",
        })
        return feature
    finally:
        builder.Destroy()


def create_circular_pattern(work_part, seed_feature, side: str):
    builder = work_part.Features.CreatePatternFeatureBuilder(NXOpen.Features.Feature.Null)
    try:
        builder.FeatureList.Add([seed_feature])
        builder.PatternMethod = NXOpen.Features.PatternFeatureBuilder.PatternMethodOptions.Simple
        service = builder.PatternService
        service.PatternType = NXOpen.GeometricUtilities.PatternDefinition.PatternEnum.Circular
        circular = service.CircularDefinition
        circular.AngularSpacing.NCopies.SetFormula("STEP2_HOLES_PER_FLANGE")
        circular.AngularSpacing.PitchAngle.SetFormula("STEP2_HOLE_PITCH")
        axis_direction = work_part.Directions.CreateDirection(
            NXOpen.Point3d(0.0, 0.0, 0.0),
            NXOpen.Vector3d(1.0, 0.0, 0.0),
            NXOpen.SmartObject.UpdateOption.WithinModeling,
        )
        circular.RotationAxis = work_part.Axes.CreateAxis(
            NXOpen.Point.Null, axis_direction, NXOpen.SmartObject.UpdateOption.WithinModeling
        )
        circular.HorizontalRef.RotationAngle.SetFormula("0")
        feature = builder.Commit()
        feature.SetName(side + "_STAP2_FLANGE_HOLE_PATTERN")
        set_attributes(feature, {
            "ELSTER_CAM_RULE_SCHEMA": CAM_RULE_SCHEMA,
            "ELSTER_CAM_FEATURE_ID": "STAP2_{}_FLANGE_HOLE_PATTERN".format(side),
            "ELSTER_CAM_FEATURE_CLASS": "CIRCULAR_HOLE_PATTERN",
            "ELSTER_CAM_PROCESS": "AXIAL_FLANGE_HOLEMAKING",
            "ELSTER_CAM_STEP": STEP_NAME,
            "ELSTER_CAM_SIDE": side,
            "ELSTER_NATIVE_FEATURE_TYPE": "CIRCULAR FEATURE PATTERN",
            "ELSTER_CAM_COUNT_EXPRESSION": "STEP2_HOLES_PER_FLANGE",
            "ELSTER_CAM_PITCH_EXPRESSION": "STEP2_HOLE_PITCH",
        })
        return feature
    finally:
        builder.Destroy()


def verify_chamfers(work_part, hole_features, diameter):
    readbacks = []
    for feature in hole_features:
        builder = work_part.Features.CreateHolePackageBuilder(feature)
        try:
            for side in ("Start", "End"):
                enabled = bool(getattr(builder, "Custom" + side + "ChamferEnabled"))
                offset = float(getattr(builder, "Custom" + side + "ChamferOffset").Value)
                angle = float(getattr(builder, "Custom" + side + "ChamferAngle").Value)
                if not enabled or not math.isclose(offset, 0.2, abs_tol=1e-8) or not math.isclose(angle, 45.0, abs_tol=1e-8):
                    raise RuntimeError("STAP2 kantbreking readback wijkt af.")
                readbacks.append({"feature": feature.Name, "end": side, "offset_mm": offset, "angle_deg": angle})
        finally:
            builder.Destroy()
    uf = NXOpen.UF.UFSession.GetUFSession()
    counts = {}
    for body in work_part.Bodies:
        for face in body.GetFaces():
            kind, point, direction, box, radius, radial_data, norm = uf.Modeling.AskFaceData(face.Tag)
            if kind != 17 or abs(direction[0]) < 0.999:
                continue
            if not math.isclose(box[3] - box[0], 0.2, abs_tol=0.001):
                continue
            if not all(math.isclose(box[i+3] - box[i], diameter + 0.4, abs_tol=0.001) for i in (1, 2)):
                continue
            x = round((box[0] + box[3]) / 2, 3)
            counts[str(x)] = counts.get(str(x), 0) + 1
    if len(counts) != 4 or any(count != 12 for count in counts.values()):
        raise RuntimeError("48 conische kantbrekingen verwacht, 12 per flenszijde; gevonden: " + str(counts))
    return {"passed": True, "conical_face_count": sum(counts.values()), "faces_per_axial_plane": counts, "seed_builder_readback": readbacks}

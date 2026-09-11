"""Active builders extracted from elster_family/nx_step3_centerbody_flats_journal.py."""

from __future__ import annotations

import NXOpen
import NXOpen.Features
import NXOpen.GeometricUtilities

from .common import scalar_expression as _scalar, set_attributes

STEP_NAME = "STAP3_CENTERBODY_FLATS"
CAM_RULE_SCHEMA = "ELSTER_CAM_RULES_V1"


def _coordinate_expression(work_part, name: str, formula: str):
    units_mm = work_part.UnitCollection.FindObject("MilliMeter")
    return work_part.Expressions.CreateNumberExpression(name + " = " + formula, units_mm)


def _point(work_part, feature_id: str, index: int, formulas):
    names = []
    for axis, formula in zip(("X", "Y", "Z"), formulas):
        name = "STAP3_{}_P{}_{}".format(feature_id, index, axis)
        _coordinate_expression(work_part, name, formula)
        names.append(name)
    point = work_part.Points.CreatePoint(
        _scalar(work_part, names[0]),
        _scalar(work_part, names[1]),
        _scalar(work_part, names[2]),
        NXOpen.SmartObject.UpdateOption.WithinModeling,
    )
    point.SetName("{}_CUTTER_P{}".format(feature_id, index))
    return point


def _create_profile(work_part, feature_id: str, point_formulas):
    points = [
        _point(work_part, feature_id, index, formulas)
        for index, formulas in enumerate(point_formulas, 1)
    ]
    lines = [
        work_part.Curves.CreateLine(points[0], points[1]),
        work_part.Curves.CreateLine(points[1], points[2]),
        work_part.Curves.CreateLine(points[2], points[3]),
        work_part.Curves.CreateLine(points[3], points[0]),
    ]
    for index, line in enumerate(lines, 1):
        line.SetName("{}_CUTTER_EDGE_{}".format(feature_id, index))
    return lines


def _create_subtract_extrude(
    work_part,
    body,
    feature_id: str,
    point_formulas,
    direction_vector,
    start_extend: str,
    end_extend: str,
    side_label: str,
    offset_expression: str,
):
    curves = _create_profile(work_part, feature_id, point_formulas)
    section = work_part.Sections.CreateSection(0.0095, 0.01, 0.5)
    section.SetAllowedEntityTypes(NXOpen.Section.AllowTypes.OnlyCurves)
    section.AllowSelfIntersection(False)
    section.AllowDegenerateCurves(False)
    options = work_part.ScRuleFactory.CreateRuleOptions()
    options.SetSelectedFromInactive(False)
    rule = work_part.ScRuleFactory.CreateRuleBaseCurveDumb(curves, options)
    section.AddToSection(
        [rule], curves[0], NXOpen.NXObject.Null, NXOpen.NXObject.Null,
        curves[0].StartPoint, NXOpen.Section.Mode.Create, False,
    )
    options.Dispose()
    direction = work_part.Directions.CreateDirection(
        NXOpen.Point3d(0.0, 0.0, 0.0),
        direction_vector,
        NXOpen.SmartObject.UpdateOption.WithinModeling,
    )
    builder = work_part.Features.CreateExtrudeBuilder(NXOpen.Features.Feature.Null)
    builder.Section = section
    builder.Direction = direction
    builder.Limits.StartExtend.Value.RightHandSide = start_extend
    builder.Limits.EndExtend.Value.RightHandSide = end_extend
    builder.BooleanOperation.Type = NXOpen.GeometricUtilities.BooleanOperation.BooleanType.Subtract
    builder.BooleanOperation.SetTargetBodies([body])
    try:
        feature = builder.CommitFeature()
    finally:
        builder.Destroy()
        section.Destroy()
    feature.SetName(feature_id)
    set_attributes(feature, {
        "ELSTER_CAM_RULE_SCHEMA": CAM_RULE_SCHEMA,
        "ELSTER_CAM_FEATURE_ID": feature_id,
        "ELSTER_CAM_FEATURE_CLASS": "PLANAR_MILLING_FLAT",
        "ELSTER_CAM_PROCESS": "PLANAR_MILLING",
        "ELSTER_CAM_STEP": STEP_NAME,
        "ELSTER_CAM_SIDE": side_label,
        "ELSTER_NATIVE_FEATURE_TYPE": "EXTRUDE SUBTRACT",
        "ELSTER_CAM_OFFSET_EXPRESSION": offset_expression,
        "ELSTER_CAM_TOPOLOGY": "ONE_CENTER_FOUR_DIAGONAL_FOUR_SIDE_FLATS",
    })
    return feature


def build(work_part):
    body = list(work_part.Bodies)[0]
    features = []
    _coordinate_expression(work_part, "STAP3_BODY_RADIUS", "125")

    features.append(_create_subtract_extrude(
        work_part, body, "STAP3_CENTER_PAD_FLAT",
        [
            ("-STEP3_CENTER_PAD_HALF_WIDTH", "-sqrt(STAP3_BODY_RADIUS * STAP3_BODY_RADIUS - STEP3_FLAT_OFFSET * STEP3_FLAT_OFFSET)", "STEP3_FLAT_OFFSET"),
            ("STEP3_CENTER_PAD_HALF_WIDTH", "-sqrt(STAP3_BODY_RADIUS * STAP3_BODY_RADIUS - STEP3_FLAT_OFFSET * STEP3_FLAT_OFFSET)", "STEP3_FLAT_OFFSET"),
            ("STEP3_CENTER_PAD_HALF_WIDTH", "sqrt(STAP3_BODY_RADIUS * STAP3_BODY_RADIUS - STEP3_FLAT_OFFSET * STEP3_FLAT_OFFSET)", "STEP3_FLAT_OFFSET"),
            ("-STEP3_CENTER_PAD_HALF_WIDTH", "sqrt(STAP3_BODY_RADIUS * STAP3_BODY_RADIUS - STEP3_FLAT_OFFSET * STEP3_FLAT_OFFSET)", "STEP3_FLAT_OFFSET"),
        ],
        NXOpen.Vector3d(0.0, 0.0, 1.0),
        "0", "FA / 2 + 100", "CENTRAL", "STEP3_FLAT_OFFSET",
    ))

    side_x_zones = (
        ("POS_X", "STEP3_SIDE_PAD_Y_CENTER - STEP3_SIDE_PAD_Y_WIDTH / 2", "STEP3_SIDE_PAD_Y_CENTER + STEP3_SIDE_PAD_Y_WIDTH / 2"),
        ("NEG_X", "-STEP3_SIDE_PAD_Y_CENTER - STEP3_SIDE_PAD_Y_WIDTH / 2", "-STEP3_SIDE_PAD_Y_CENTER + STEP3_SIDE_PAD_Y_WIDTH / 2"),
    )
    side_specs = []
    for y_side, y_formula, direction_vector in (
        ("POS_Y", "STEP3_SIDE_FLAT_OFFSET", NXOpen.Vector3d(0.0, 1.0, 0.0)),
        ("NEG_Y", "-STEP3_SIDE_FLAT_OFFSET", NXOpen.Vector3d(0.0, -1.0, 0.0)),
    ):
        for x_side, x_low, x_high in side_x_zones:
            feature_id = "STAP3_SIDE_{}_{}".format(y_side, x_side)
            side_specs.append((
                _create_subtract_extrude,
                work_part, body, feature_id,
                [
                    (x_low, y_formula, "-STEP3_DIAGONAL_TANGENT_HALF"),
                    (x_high, y_formula, "-STEP3_DIAGONAL_TANGENT_HALF"),
                    (x_high, y_formula, "STEP3_DIAGONAL_TANGENT_HALF"),
                    (x_low, y_formula, "STEP3_DIAGONAL_TANGENT_HALF"),
                ],
                direction_vector,
                "0", "FA / 2 + 100", y_side + "_" + x_side, "STEP3_SIDE_FLAT_OFFSET",
            ))

    diagonal_x_zones = (
        ("POS_X", "STEP3_DIAGONAL_PAD_Y_CENTER - STEP3_DIAGONAL_PAD_Y_WIDTH / 2", "STEP3_DIAGONAL_PAD_Y_CENTER + STEP3_DIAGONAL_PAD_Y_WIDTH / 2"),
        ("NEG_X", "-STEP3_DIAGONAL_PAD_Y_CENTER - STEP3_DIAGONAL_PAD_Y_WIDTH / 2", "-STEP3_DIAGONAL_PAD_Y_CENTER + STEP3_DIAGONAL_PAD_Y_WIDTH / 2"),
    )
    for diagonal_side in ("POS_Y", "NEG_Y"):
        if diagonal_side == "POS_Y":
            normal = NXOpen.Vector3d(0.0, 1.0 / 1.4142135623730951, 1.0 / 1.4142135623730951)
            base_y = "STEP3_SIDE_FLAT_OFFSET / 1.4142135623730951"
            base_z = "STEP3_SIDE_FLAT_OFFSET / 1.4142135623730951"
            tangent_y = "1 / 1.4142135623730951"
            tangent_z = "-1 / 1.4142135623730951"
        else:
            normal = NXOpen.Vector3d(0.0, -1.0 / 1.4142135623730951, 1.0 / 1.4142135623730951)
            base_y = "-STEP3_SIDE_FLAT_OFFSET / 1.4142135623730951"
            base_z = "STEP3_SIDE_FLAT_OFFSET / 1.4142135623730951"
            tangent_y = "1 / 1.4142135623730951"
            tangent_z = "1 / 1.4142135623730951"
        for x_side, x_low, x_high in diagonal_x_zones:
            feature_id = "STAP3_DIAGONAL_{}_{}".format(diagonal_side, x_side)
            points = [
                (x_low, "{} - STEP3_DIAGONAL_TANGENT_HALF * ({})".format(base_y, tangent_y), "{} - STEP3_DIAGONAL_TANGENT_HALF * ({})".format(base_z, tangent_z)),
                (x_high, "{} - STEP3_DIAGONAL_TANGENT_HALF * ({})".format(base_y, tangent_y), "{} - STEP3_DIAGONAL_TANGENT_HALF * ({})".format(base_z, tangent_z)),
                (x_high, "{} + STEP3_DIAGONAL_TANGENT_HALF * ({})".format(base_y, tangent_y), "{} + STEP3_DIAGONAL_TANGENT_HALF * ({})".format(base_z, tangent_z)),
                (x_low, "{} + STEP3_DIAGONAL_TANGENT_HALF * ({})".format(base_y, tangent_y), "{} + STEP3_DIAGONAL_TANGENT_HALF * ({})".format(base_z, tangent_z)),
            ]
            features.append(_create_subtract_extrude(
                work_part, body, feature_id, points,
                normal, "0", "FA / 2 + 100",
                diagonal_side + "_" + x_side, "STEP3_SIDE_FLAT_OFFSET",
            ))

    # The reference feature order cuts the diagonal pads before the side pads.
    # Keeping this order avoids deleting the small overlap that makes each
    # diagonal cutter unambiguously intersect the STAP2 solid.
    for creator, *args in side_specs:
        features.append(creator(*args))
    return features

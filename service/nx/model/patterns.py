"""Active placement constructors extracted from elster_family/step7-9.

Numeric placement records are descriptive; named expressions drive NX points.
"""

from __future__ import annotations

from typing import Any


def step7_positions() -> list[dict[str, Any]]:
    x_positions = (
        ("OUTER_NEG", "STEP7_M8_OUTER_NEG_X", -180.0),
        ("INNER_NEG", "STEP7_M8_INNER_NEG_X", -70.0),
        ("INNER_POS", "STEP7_M8_INNER_POS_X", 70.0),
        ("OUTER_POS", "STEP7_M8_OUTER_POS_X", 180.0),
    )
    y_positions = (
        ("NEG_Y", -20.0, "STEP7_M8_NEG_Y"),
        ("POS_Y", 20.0, "STEP7_M8_POS_Y"),
    )
    result = []
    for side, z_expression, z_mm, probe_expression, direction in (
        ("Z_POS", "STEP7_M8_ENTRY_Z_POS", 120.0, "STEP7_M8_PROBE_Z_POS", "GLOBAL_MINUS_Z_INWARD"),
        ("Z_NEG", "STEP7_M8_ENTRY_Z_NEG", -120.0, "STEP7_M8_PROBE_Z_NEG", "GLOBAL_PLUS_Z_INWARD"),
    ):
        for y_id, y_mm, y_expression in y_positions:
            for x_id, x_expression, x_mm in x_positions:
                result.append({
                    "position_id": "M8_{}_{}_{}".format(side, y_id, x_id),
                    "side": side,
                    "x_expression": x_expression,
                    "x_mm": x_mm,
                    "y_expression": y_expression,
                    "y_mm": y_mm,
                    "entry_z_expression": z_expression,
                    "entry_z_mm": z_mm,
                    "probe_z_expression": probe_expression,
                    "probe_z_mm": 130.0 if side == "Z_POS" else -130.0,
                    "access_vector": direction,
                })
    return result


def step8_positions() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    faces = (
        ("POS_Y_POS_X", "POS_Y", "STEP8_DIAGONAL_FACE_CENTER_X", 153.0, "DIAGONAL_POS_Y_INWARD"),
        ("POS_Y_NEG_X", "POS_Y", "-STEP8_DIAGONAL_FACE_CENTER_X", -153.0, "DIAGONAL_POS_Y_INWARD"),
        ("NEG_Y_POS_X", "NEG_Y", "STEP8_DIAGONAL_FACE_CENTER_X", 153.0, "DIAGONAL_NEG_Y_INWARD"),
        ("NEG_Y_NEG_X", "NEG_Y", "-STEP8_DIAGONAL_FACE_CENTER_X", -153.0, "DIAGONAL_NEG_Y_INWARD"),
    )
    holes = (
        ("M8_NEG", "M8", "-STEP8_DIAGONAL_PATTERN_HALF_PITCH", -22.5),
        ("H9_CENTER", "H9", "0", 0.0),
        ("M8_POS", "M8", "STEP8_DIAGONAL_PATTERN_HALF_PITCH", 22.5),
    )
    for face_id, plane_side, x_expression, x_mm, access_vector in faces:
        for role, hole_type, offset_expression, offset_mm in holes:
            result.append({
                "position_id": "DIAGONAL_{}_{}".format(face_id, role),
                "face_id": "STAP3_DIAGONAL_{}".format(face_id),
                "plane_side": plane_side,
                "hole_type": hole_type,
                "role": role,
                "x_expression": x_expression,
                "x_mm": x_mm,
                "tangent_offset_expression": offset_expression,
                "tangent_offset_mm": offset_mm,
                "access_vector": access_vector,
            })
    return result


def step9_positions() -> list[dict[str, Any]]:
    faces = (
        ("POS_Y_POS_X", "POS_Y", "POS_X", "INNER", "STEP9_SIDE_HOLE_INNER_X", 104.76, -1, "SIDE_POS_Y_INWARD"),
        ("POS_Y_POS_X", "POS_Y", "POS_X", "OUTER", "STEP9_SIDE_HOLE_OUTER_X", 144.76, 1, "SIDE_POS_Y_INWARD"),
        ("POS_Y_NEG_X", "POS_Y", "NEG_X", "INNER", "-STEP9_SIDE_HOLE_INNER_X", -104.76, -1, "SIDE_POS_Y_INWARD"),
        ("POS_Y_NEG_X", "POS_Y", "NEG_X", "OUTER", "-STEP9_SIDE_HOLE_OUTER_X", -144.76, 1, "SIDE_POS_Y_INWARD"),
        ("NEG_Y_POS_X", "NEG_Y", "POS_X", "INNER", "STEP9_SIDE_HOLE_INNER_X", 104.76, -1, "SIDE_NEG_Y_INWARD"),
        ("NEG_Y_POS_X", "NEG_Y", "POS_X", "OUTER", "STEP9_SIDE_HOLE_OUTER_X", 144.76, 1, "SIDE_NEG_Y_INWARD"),
        ("NEG_Y_NEG_X", "NEG_Y", "NEG_X", "INNER", "-STEP9_SIDE_HOLE_INNER_X", -104.76, -1, "SIDE_NEG_Y_INWARD"),
        ("NEG_Y_NEG_X", "NEG_Y", "NEG_X", "OUTER", "-STEP9_SIDE_HOLE_OUTER_X", -144.76, 1, "SIDE_NEG_Y_INWARD"),
    )
    holes = (("M8_NEG", "M8", -1), ("H9_CENTER", "H9", 0), ("M8_POS", "M8", 1))
    result: list[dict[str, Any]] = []
    for face_id, plane_side, axial_zone, axial_position, x_expression, x_mm, stagger_sign, access_vector in faces:
        center_expression = "STEP9_SIDE_PATTERN_STAGGER" if stagger_sign > 0 else "-STEP9_SIDE_PATTERN_STAGGER"
        center_mm = stagger_sign * 1.38
        for role, hole_type, pitch_sign in holes:
            if pitch_sign < 0:
                offset_expression = center_expression + " - STEP9_SIDE_PATTERN_HALF_PITCH"
            elif pitch_sign > 0:
                offset_expression = center_expression + " + STEP9_SIDE_PATTERN_HALF_PITCH"
            else:
                offset_expression = center_expression
            offset_mm = center_mm + pitch_sign * 22.5
            result.append({
                "position_id": f"SIDE_{face_id}_{axial_position}_{role}",
                "face_id": f"STAP3_SIDE_{face_id}",
                "plane_side": plane_side,
                "axial_zone": axial_zone,
                "axial_position": axial_position,
                "hole_type": hole_type,
                "role": role,
                "x_expression": x_expression,
                "x_mm": x_mm,
                "stagger_sign": stagger_sign,
                "local_center_expression": center_expression,
                "local_center_mm": center_mm,
                "pitch_sign": pitch_sign,
                "tangent_offset_expression": offset_expression,
                "tangent_offset_mm": offset_mm,
                "access_vector": access_vector,
            })
    return result


def diagonal_formulas(position: dict[str, Any], *, probe: bool) -> dict[str, str]:
    offset = position["tangent_offset_expression"]
    margin = "STEP8_DIAGONAL_PROJECTION_MARGIN" if probe else "0"
    if position["plane_side"] == "POS_Y":
        # Plane normal is (0,+1/sqrt(2),+1/sqrt(2)); its tangent is
        # (0,+1/sqrt(2),-1/sqrt(2)).
        return {
            "x": position["x_expression"],
            "y": "STEP3_SIDE_FLAT_OFFSET / sqrt(2) + ({}) / sqrt(2) + ({}) / sqrt(2)".format(offset, margin),
            "z": "STEP3_SIDE_FLAT_OFFSET / sqrt(2) - ({}) / sqrt(2) + ({}) / sqrt(2)".format(offset, margin),
        }
    # Plane normal is (0,-1/sqrt(2),+1/sqrt(2)); its tangent is
    # (0,+1/sqrt(2),+1/sqrt(2)).
    return {
        "x": position["x_expression"],
        "y": "-STEP3_SIDE_FLAT_OFFSET / sqrt(2) + ({}) / sqrt(2) - ({}) / sqrt(2)".format(offset, margin),
        "z": "STEP3_SIDE_FLAT_OFFSET / sqrt(2) + ({}) / sqrt(2) + ({}) / sqrt(2)".format(offset, margin),
    }

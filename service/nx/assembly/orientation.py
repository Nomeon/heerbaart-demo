"""Active builders extracted from heerbaart_poc/tools/orientation.py."""

import math

from .axis import axis_name as normalize_axis_name, axis_vector

def collect_orientation_diagnostics(
    NXOpen,
    work_part,
    distance_tolerance,
    centerline_axis,
):
    target_axis_name = normalize_axis_name(centerline_axis)
    target_axis = axis_vector(target_axis_name)

    candidates = collect_centerline_candidates(NXOpen, work_part)

    if not candidates:
        raise RuntimeError(
            "No cylindrical, conical, or surface-of-revolution face found for orientation"
        )

    centerline = max(candidates, key=lambda candidate: candidate["score"])
    direction = orient_toward_axis(centerline["direction"], target_axis)
    point = centerline["point"]
    midpoint = centerline["midpoint"]
    rotation = rotation_to_axis(direction, target_axis)
    rotated_point = rotate_vector(point, rotation)
    rotated_midpoint = rotate_vector(midpoint, rotation)
    radial_offset = radial_offset_from_axis(rotated_point, target_axis)
    offset_from_target_axis = vector_length(radial_offset)
    angle_to_target_axis = angle_between_degrees(direction, target_axis)
    translation_to_target_axis = scale(radial_offset, -1.0)

    return {
        "method": "dominant_centerline",
        "targetAxis": target_axis_name,
        "correctOrientation": {
            "centerlineDirection": list(target_axis),
            "centerlineRadialOffset": [0.0, 0.0, 0.0],
        },
        "currentCenterline": {
            "point": round_vector(point),
            "midpoint": round_vector(midpoint),
            "direction": round_vector(direction),
            "angleToTargetAxis": round_float(angle_to_target_axis),
            "offsetFromTargetAxisAfterRotation": round_float(offset_from_target_axis),
            "rotatedPoint": round_vector(rotated_point),
            "rotatedMidpoint": round_vector(rotated_midpoint),
        },
        "proposedTransform": {
            "rotationAxis": round_vector(rotation["axis"]),
            "rotationAngleDegrees": round_float(rotation["angle_degrees"]),
            "translationAfterRotation": round_vector(translation_to_target_axis),
        },
        "status": {
            "isParallelToTargetAxis": angle_to_target_axis <= 0.1,
            "isOnTargetAxisAfterRotation": (
                offset_from_target_axis <= distance_tolerance
            ),
            "requiresRotation": angle_to_target_axis > 0.1,
            "requiresTranslation": offset_from_target_axis > distance_tolerance,
        },
        "dominantFace": {
            "journalIdentifier": centerline["journal_identifier"],
            "solidFaceType": centerline["solid_face_type"],
            "radius": round_float(centerline["radius"]),
            "axialSpan": round_float(centerline["axial_span"]),
            "score": round_float(centerline["score"]),
        },
        "candidateCount": len(candidates),
    }



def rotation_matrix(axis, angle, pivot):
    x, y, z = normalize(axis)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    one_minus_cosine = 1.0 - cosine

    rotation = (
        (
            one_minus_cosine * x * x + cosine,
            one_minus_cosine * x * y - sine * z,
            one_minus_cosine * x * z + sine * y,
        ),
        (
            one_minus_cosine * x * y + sine * z,
            one_minus_cosine * y * y + cosine,
            one_minus_cosine * y * z - sine * x,
        ),
        (
            one_minus_cosine * x * z - sine * y,
            one_minus_cosine * y * z + sine * x,
            one_minus_cosine * z * z + cosine,
        ),
    )

    px, py, pz = pivot
    rotated_pivot = (
        dot(rotation[0], pivot),
        dot(rotation[1], pivot),
        dot(rotation[2], pivot),
    )
    translation = (
        px - rotated_pivot[0],
        py - rotated_pivot[1],
        pz - rotated_pivot[2],
    )

    return [
        rotation[0][0], rotation[0][1], rotation[0][2], translation[0],
        rotation[1][0], rotation[1][1], rotation[1][2], translation[1],
        rotation[2][0], rotation[2][1], rotation[2][2], translation[2],
        0.0, 0.0, 0.0, 1.0,
    ]



def collect_centerline_candidates(NXOpen, work_part):
    candidates = []
    uf_session = NXOpen.UF.UFSession.GetUFSession()
    modeling = getattr(uf_session, "Modeling", uf_session.Modl)

    for body in work_part.Bodies:
        for face in body.GetFaces():
            if not is_axis_face(NXOpen, face):
                continue

            face_type, point, direction, face_radius = ask_face_axis(face, modeling)
            vertices = collect_face_vertices(face)
            midpoint, axial_span, radius = face_axis_dimensions(point, direction, vertices)
            if radius == 0.0:
                radius = face_radius

            candidates.append(
                {
                    "journal_identifier": face.JournalIdentifier,
                    "solid_face_type": str(face.SolidFaceType),
                    "uf_face_type": face_type,
                    "point": point,
                    "midpoint": midpoint,
                    "direction": direction,
                    "radius": radius,
                    "axial_span": axial_span,
                    "score": max(radius, 0.001) * max(axial_span, 0.001),
                }
            )

    return candidates



def ask_face_axis(face, modeling):
    for method_name in ("AskFaceData", "AskFaceProps"):
        method = getattr(modeling, method_name, None)

        if not method:
            continue

        try:
            face_data = method(face.Tag)
        except TypeError:
            continue

        parsed = parse_face_axis_data(face_data)

        if parsed:
            return parsed

    for method_name in ("GetData", "GetFaceData", "AskFaceData"):
        method = getattr(face, method_name, None)

        if not method:
            continue

        try:
            face_data = method()
        except TypeError:
            continue

        parsed = parse_face_axis_data(face_data)

        if parsed:
            return parsed

    raise AttributeError("No available NXOpen face-axis data method found")



def parse_face_axis_data(face_data):
    if not isinstance(face_data, tuple):
        return None

    if len(face_data) >= 4 and isinstance(face_data[0], int):
        face_type = face_data[0]
        point = tuple(float(value) for value in face_data[1])
        direction = normalize(tuple(float(value) for value in face_data[2]))
        radius = float(face_data[4]) if len(face_data) > 4 else 0.0
        return face_type, point, direction, radius

    vectors = [
        tuple(float(value) for value in item)
        for item in face_data
        if isinstance(item, (list, tuple)) and len(item) == 3
    ]

    if len(vectors) < 2:
        return None

    return None, vectors[0], normalize(vectors[1]), 0.0



def is_axis_face(NXOpen, face):
    axis_face_types = {
        NXOpen.Face.FaceType.Cylindrical,
        NXOpen.Face.FaceType.Conical,
        NXOpen.Face.FaceType.SurfaceOfRevolution,
    }
    return face.SolidFaceType in axis_face_types



def collect_face_vertices(face):
    vertices = []

    for edge in face.GetEdges():
        for vertex in edge.GetVertices():
            vertices.append(point_xyz(vertex))

    return vertices



def face_axis_dimensions(axis_point, axis_direction, vertices):
    if not vertices:
        return axis_point, 0.0, 0.0

    projections = [
        dot(subtract(vertex, axis_point), axis_direction)
        for vertex in vertices
    ]
    minimum_projection = min(projections)
    maximum_projection = max(projections)
    midpoint_projection = (minimum_projection + maximum_projection) * 0.5
    midpoint = add(axis_point, scale(axis_direction, midpoint_projection))
    radii = [
        distance_to_axis(vertex, axis_point, axis_direction)
        for vertex in vertices
    ]

    return midpoint, maximum_projection - minimum_projection, max(radii)



def point_xyz(point):
    if hasattr(point, "Coordinates"):
        point = point.Coordinates

    if isinstance(point, (list, tuple)):
        return (float(point[0]), float(point[1]), float(point[2]))

    return (float(point.X), float(point.Y), float(point.Z))



def rotation_to_axis(direction, target_axis):
    direction = normalize(direction)
    target_axis = normalize(target_axis)
    rotation_axis = cross(direction, target_axis)
    rotation_axis_length = vector_length(rotation_axis)

    if rotation_axis_length <= 1.0e-9:
        return {
            "axis": (0.0, 0.0, 1.0),
            "angle_radians": 0.0,
            "angle_degrees": 0.0,
        }

    angle_radians = math.acos(clamp(dot(direction, target_axis), -1.0, 1.0))

    return {
        "axis": scale(rotation_axis, 1.0 / rotation_axis_length),
        "angle_radians": angle_radians,
        "angle_degrees": math.degrees(angle_radians),
    }



def rotate_vector(vector, rotation):
    axis = rotation["axis"]
    angle = rotation["angle_radians"]

    if abs(angle) <= 1.0e-12:
        return vector

    cos_angle = math.cos(angle)
    sin_angle = math.sin(angle)

    return add(
        add(
            scale(vector, cos_angle),
            scale(cross(axis, vector), sin_angle),
        ),
        scale(axis, dot(axis, vector) * (1.0 - cos_angle)),
    )



def angle_between_degrees(first, second):
    return math.degrees(
        math.acos(clamp(dot(normalize(first), normalize(second)), -1.0, 1.0))
    )



def orient_toward_axis(direction, target_axis):
    direction = normalize(direction)

    if dot(direction, target_axis) < 0.0:
        return scale(direction, -1.0)

    return direction



def radial_offset_from_axis(point, axis_direction):
    projection = scale(axis_direction, dot(point, axis_direction))
    return subtract(point, projection)



def distance_to_axis(point, axis_point, axis_direction):
    offset = subtract(point, axis_point)
    projection = scale(axis_direction, dot(offset, axis_direction))
    radial = subtract(offset, projection)
    return vector_length(radial)



def normalize(vector):
    length = vector_length(vector)

    if length <= 1.0e-12:
        raise ValueError("Cannot normalize zero-length vector")

    return scale(vector, 1.0 / length)



def add(first, second):
    return (
        first[0] + second[0],
        first[1] + second[1],
        first[2] + second[2],
    )



def subtract(first, second):
    return (
        first[0] - second[0],
        first[1] - second[1],
        first[2] - second[2],
    )



def scale(vector, factor):
    return (
        vector[0] * factor,
        vector[1] * factor,
        vector[2] * factor,
    )



def dot(first, second):
    return (
        first[0] * second[0]
        + first[1] * second[1]
        + first[2] * second[2]
    )



def cross(first, second):
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )



def vector_length(vector):
    return math.sqrt(dot(vector, vector))



def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))



def round_vector(vector):
    return [round_float(value) for value in vector]



def round_float(value):
    return round(float(value), 6)

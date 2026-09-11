"""Active builders extracted from heerbaart_poc/tools/blank.py."""

from .axis import perpendicular_axis_vector
from .orientation import point_xyz, subtract, scale, dot


def point_radius(point, target_axis):
    return radial_distance_from_axis(point_xyz(point), target_axis)



def create_revolve_outline_blank(
    NXOpen,
    work_part,
    body,
    distance_tolerance,
    offset_distance,
    target_axis,
):
    axis_face = find_axis_face(NXOpen, body, target_axis)
    outline_feature = create_revolve_outline(
        NXOpen,
        work_part,
        body,
        axis_face,
        distance_tolerance,
        target_axis,
    )
    outline_feature.SetName("BLANK_REVOLVE_OUTLINE")
    section = create_full_outline_section(
        NXOpen,
        work_part,
        outline_feature,
        distance_tolerance,
        target_axis,
    )
    blank_feature = revolve_section(
        NXOpen,
        work_part,
        section,
        distance_tolerance,
        target_axis,
    )
    blank_feature.SetName("BLANK_REVOLVE")
    offset_blank_region(NXOpen, work_part, blank_feature, offset_distance)
    return list(blank_feature.GetBodies())



def find_axis_face(NXOpen, body, target_axis):
    axis_face_types = {
        NXOpen.Face.FaceType.Cylindrical,
        NXOpen.Face.FaceType.Conical,
        NXOpen.Face.FaceType.SurfaceOfRevolution,
    }
    candidates = []

    for face in body.GetFaces():
        if face.SolidFaceType in axis_face_types:
            candidates.append((face_axis_score(face, target_axis), face))

    if not candidates:
        raise RuntimeError("The linked CAD4CAM body has no Revolve Outline axis face")
    return max(candidates, key=lambda candidate: candidate[0])[1]



def face_axis_score(face, target_axis):
    points = []

    for edge in face.GetEdges():
        points.extend(point_xyz(vertex) for vertex in edge.GetVertices())

    max_radius = max(radial_distance_from_axis(point, target_axis) for point in points)
    axial_values = [dot(point, target_axis) for point in points]
    return (max_radius, max(axial_values) - min(axial_values))



def create_body_rule(work_part, body):
    rule_options = work_part.ScRuleFactory.CreateRuleOptions()
    rule_options.SetSelectedFromInactive(False)
    body_rule = work_part.ScRuleFactory.CreateRuleBodyDumb(
        [body],
        True,
        rule_options,
    )
    rule_options.Dispose()
    return body_rule



def create_revolve_outline(
    NXOpen,
    work_part,
    body,
    axis_face,
    distance_tolerance,
    target_axis,
):
    builder = work_part.Features.CurveFeatureCollection.CreateRevolveOutlineBuilder(
        NXOpen.Features.RevolveOutline.Null
    )
    builder.TargetBodies.ReplaceRules([create_body_rule(work_part, body)], False)
    builder.AxisFace.Value = axis_face
    builder.DistanceTol = distance_tolerance
    builder.PlaneNormal = create_direction(
        NXOpen,
        work_part,
        perpendicular_axis_vector(target_axis),
    )
    outline_feature = builder.Commit()
    builder.Destroy()
    return outline_feature



def curve_score_points(curve):
    points = []

    if hasattr(curve, "StartPoint"):
        points.append(curve.StartPoint)

    if hasattr(curve, "EndPoint"):
        points.append(curve.EndPoint)

    if hasattr(curve, "CenterPoint"):
        points.append(curve.CenterPoint)

    if not points:
        try:
            points.append(curve.NameLocation)
        except Exception:
            return []

    return points



def seed_score(curve, target_axis):
    return max(
        (point_radius(point, target_axis) for point in curve_score_points(curve)),
        default=0.0,
    )



def axial_bounds(curves, target_axis):
    values = [
        dot(point_xyz(point), target_axis)
        for curve in curves
        for point in curve_score_points(curve)
    ]
    if not values:
        raise RuntimeError("Cannot determine outline section axial coverage")
    return min(values), max(values)



def curve_help_point(NXOpen, curve):
    if hasattr(curve, "StartPoint") and hasattr(curve, "EndPoint"):
        start = curve.StartPoint
        end = curve.EndPoint
        return NXOpen.Point3d(
            (start.X + end.X) * 0.5,
            (start.Y + end.Y) * 0.5,
            (start.Z + end.Z) * 0.5,
        )

    if hasattr(curve, "CenterPoint"):
        return curve.CenterPoint

    return NXOpen.Point3d(0.0, 0.0, 0.0)



def outline_seed_candidates(outline_feature, target_axis, distance_tolerance):
    curves = [
        entity
        for entity in outline_feature.GetEntities()
        if hasattr(entity, "GetLength")
    ]

    if not curves:
        raise RuntimeError("Native revolve outline did not create selectable curves")

    scores = [(curve, seed_score(curve, target_axis)) for curve in curves]
    max_radius = max(score for _, score in scores)
    candidates = [
        curve for curve, score in scores
        if max_radius - score <= distance_tolerance
    ]

    def rank(curve):
        low, high = axial_bounds([curve], target_axis)
        return high - low, curve.GetLength()

    return sorted(candidates, key=rank, reverse=True), axial_bounds(curves, target_axis)



def create_full_outline_section(
    NXOpen, work_part, outline_feature, distance_tolerance, target_axis,
):
    candidates, expected = outline_seed_candidates(
        outline_feature, target_axis, distance_tolerance,
    )
    for seed_curve in candidates:
        section = create_outline_chain_section(
            NXOpen, work_part, outline_feature, seed_curve, distance_tolerance,
        )
        try:
            curves = list(section.GetOutputCurves())
            if curves:
                actual = axial_bounds(curves, target_axis)
                if all(
                    abs(actual[index] - expected[index]) <= distance_tolerance
                    for index in (0, 1)
                ):
                    return section
        except Exception:
            section.Destroy()
            raise
        section.Destroy()

    raise RuntimeError(
        f"No outermost outline chain covers the full axial range "
        f"{expected[0]:.3f} to {expected[1]:.3f} "
        f"after checking {len(candidates)} seed curves"
    )



def create_outline_chain_section(
    NXOpen,
    work_part,
    outline_feature,
    seed_curve,
    distance_tolerance,
):
    section = work_part.Sections.CreateSection(0.0095, distance_tolerance, 0.5)
    section.DistanceTolerance = distance_tolerance
    section.ChainingTolerance = 0.0095
    section.SetAllowedEntityTypes(NXOpen.Section.AllowTypes.OnlyCurves)
    section.AllowSelfIntersection(False)
    section.AllowDegenerateCurves(False)

    rule_options = work_part.ScRuleFactory.CreateRuleOptions()
    rule_options.SetSelectedFromInactive(False)

    try:
        chain_rule = work_part.ScRuleFactory.CreateRuleCurveFeatureChain(
            [outline_feature],
            seed_curve,
            NXOpen.Curve.Null,
            False,
            0.0095,
            rule_options,
        )
        help_point = curve_help_point(NXOpen, seed_curve)
        section.AddToSection(
            [chain_rule],
            seed_curve,
            NXOpen.NXObject.Null,
            NXOpen.NXObject.Null,
            help_point,
            NXOpen.Section.Mode.Create,
            False,
        )
    except Exception:
        section.Destroy()
        raise
    finally:
        rule_options.Dispose()

    return section



def revolve_section(NXOpen, work_part, section, distance_tolerance, target_axis):
    builder = work_part.Features.CreateRevolveBuilder(NXOpen.Features.Feature.Null)
    builder.Limits.StartExtend.Value.SetFormula("0")
    builder.Limits.EndExtend.Value.SetFormula("360")
    builder.BooleanOperation.Type = (
        NXOpen.GeometricUtilities.BooleanOperation.BooleanType.Create
    )
    builder.Offset.StartOffset.SetFormula("0")
    builder.Offset.EndOffset.SetFormula("0")
    builder.Tolerance = distance_tolerance
    builder.Section = section
    builder.SmartVolumeProfile.OpenProfileSmartVolumeOption = False
    builder.SmartVolumeProfile.CloseProfileRule = (
        NXOpen.GeometricUtilities.SmartVolumeProfileBuilder.CloseProfileRuleType.Fci
    )
    builder.SetStartLimitHelperPoint([0.0, 0.0, 0.0])
    builder.SetEndLimitHelperPoint([0.0, 0.0, 0.0])
    builder.Axis = create_model_axis(NXOpen, work_part, target_axis)
    builder.ParentFeatureInternal = False
    blank_feature = builder.CommitFeature()
    builder.Destroy()
    return blank_feature



def create_model_axis(NXOpen, work_part, target_axis):
    direction = create_direction(NXOpen, work_part, target_axis)
    point = work_part.Points.CreatePoint(NXOpen.Point3d(0.0, 0.0, 0.0))
    return work_part.Axes.CreateAxis(
        point,
        direction,
        NXOpen.SmartObject.UpdateOption.WithinModeling,
    )



def create_direction(NXOpen, work_part, vector):
    return work_part.Directions.CreateDirection(
        NXOpen.Point3d(0.0, 0.0, 0.0),
        NXOpen.Vector3d(float(vector[0]), float(vector[1]), float(vector[2])),
        NXOpen.SmartObject.UpdateOption.WithinModeling,
    )



def radial_distance_from_axis(point, target_axis):
    projection = scale(target_axis, dot(point, target_axis))
    radial = subtract(point, projection)
    return vector_length(radial)



def offset_blank_region(NXOpen, work_part, blank_feature, offset_distance):
    builder = work_part.Features.CreateAdmOffsetRegionBuilder(
        NXOpen.Features.AdmOffsetRegion.Null
    )
    builder.FaceToOffset.RelationScope = 1023
    builder.FaceToOffset.CoplanarEnabled = False
    builder.FaceToOffset.CoplanarAxesEnabled = False
    builder.FaceToOffset.CoaxialEnabled = False
    builder.FaceToOffset.SameOrbitEnabled = False
    builder.FaceToOffset.EqualDiameterEnabled = False
    builder.FaceToOffset.TangentEnabled = False
    builder.FaceToOffset.SymmetricEnabled = False
    builder.FaceToOffset.OffsetEnabled = False
    builder.FaceToOffset.RigidBodyFaceEnabled = False
    builder.FaceToOffset.UseFaceBrowse = True
    builder.FaceToOffset.CloneScope = 511
    builder.FaceToOffset.VirtualFaceCollector.ReplaceRules([], False)
    builder.FaceToOffset.FaceCollector.ReplaceRules(
        [create_face_rule(work_part, list(blank_feature.GetFaces()))],
        False,
    )
    builder.Distance.SetFormula(str(offset_distance))
    builder.Commit()
    builder.Destroy()



def create_face_rule(work_part, faces):
    rule_options = work_part.ScRuleFactory.CreateRuleOptions()
    rule_options.SetSelectedFromInactive(False)
    face_rule = work_part.ScRuleFactory.CreateRuleFaceDumb(faces, rule_options)
    rule_options.Dispose()
    return face_rule



def vector_length(vector):
    return dot(vector, vector) ** 0.5

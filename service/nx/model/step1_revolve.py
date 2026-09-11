"""Active builders extracted from elster_family/nx_step1_revolve_outline_journal.py."""

from __future__ import annotations

import os

import NXOpen
import NXOpen.Features
import NXOpen.GeometricUtilities

from .common import set_attributes

STEP_NAME = "STAP1_REVOLVE_OUTLINE"
CAM_RULE_SCHEMA = "ELSTER_CAM_RULES_V1"

def create_part(session, output_path: str):
    if os.path.exists(output_path):
        raise FileExistsError(output_path)
    builder = session.Parts.FileNew()
    builder.TemplateFileName = "model-plain-1-mm-template.prt"
    builder.ApplicationName = "ModelTemplate"
    builder.Units = NXOpen.Part.Units.Millimeters
    builder.RelationType = ""
    builder.UsesMasterModel = "No"
    builder.TemplateType = NXOpen.FileNewTemplateType.Item
    builder.NewFileName = output_path
    builder.MasterFileName = ""
    builder.MakeDisplayedPart = True
    builder.DisplayPartOption = NXOpen.DisplayPartOption.AllowAdditional
    builder.Commit()
    builder.Destroy()
    return session.Parts.Work


def create_sketch(work_part, name: str):
    builder = work_part.Sketches.CreateSketchInPlaceBuilder2(NXOpen.Sketch.Null)
    plane = work_part.Planes.CreatePlane(
        NXOpen.Point3d(0.0, 0.0, 0.0),
        NXOpen.Vector3d(0.0, 0.0, 1.0),
        NXOpen.SmartObject.UpdateOption.WithinModeling,
    )
    builder.PlaneOrFace.Value = plane
    sketch = builder.Commit()
    builder.Destroy()
    sketch.SetName(name)
    return sketch


def create_profile(work_part, sketch, contract: dict):
    points = contract["profile"]["points"]
    segments = contract["profile"]["segments"]
    curves = []
    sketch.Activate(NXOpen.Sketch.ViewReorient.FalseValue)
    units_mm = work_part.UnitCollection.FindObject("MilliMeter")
    # Use associative scalar-expression points as the profile drivers.  NX's
    # sketch dimensional solver can report driving dimensions while retaining
    # the original coordinates; associative points do not have that failure
    # mode and regenerate the revolve when a table expression changes.
    point_formulas = {
        "P00": ("-600 / 2", "269.9 / 2"),
        "P01": ("-600 / 2 + FR", "269.9 / 2"),
        "P02": ("-600 / 2 + FR", "FA / 2"),
        "P03": ("-600 / 2 + FR + FB", "FA / 2"),
        "P04": ("-600 / 2 + FR + FB", "DR / 2"),
        "P05": ("-600 / 2 + FR + FB + (DR - 250) / 2", "250 / 2"),
        "P06": ("600 / 2 - FR - FB - (DR - 250) / 2", "250 / 2"),
        "P07": ("600 / 2 - FR - FB", "DR / 2"),
        "P08": ("600 / 2 - FR - FB", "FA / 2"),
        "P09": ("600 / 2 - FR", "FA / 2"),
        "P10": ("600 / 2 - FR", "269.9 / 2"),
        "P11": ("600 / 2", "269.9 / 2"),
        "P12": ("600 / 2", "DT / 2"),
        "P13": ("600 / 2 - ((DT - 180) / (2 * 0.1227845609))", "180 / 2"),
        "P14": ("-600 / 2 + ((DT - 180) / (2 * 0.1227845609))", "180 / 2"),
        "P15": ("-600 / 2", "DT / 2"),
        "P16": ("-600 / 2", "269.9 / 2"),
    }
    point_objects = {}
    expression_cache = {}
    def scalar_for(formula, label):
        key = str(formula)
        expression = expression_cache.get(key)
        if expression is None:
            try:
                expression = work_part.Expressions.CreateNumberExpression(
                    "MODEL_{} = {}".format(label, formula), units_mm
                )
            except Exception as exc:
                raise RuntimeError("Kan model-hulpexpression niet maken: {} = {} ({})".format(label, formula, exc))
            expression_cache[key] = expression
        return work_part.Scalars.CreateScalarExpression(
            expression, NXOpen.Scalar.DimensionalityType.Length,
            NXOpen.SmartObject.UpdateOption.WithinModeling,
        )
    zero_scalar = scalar_for("0", "ZERO")
    for point in points:
        name = point["name"]
        x_formula, y_formula = point_formulas[name]
        x_scalar = scalar_for(x_formula, "X_{}".format(name))
        y_scalar = scalar_for(y_formula, "Y_{}".format(name))
        point_objects[name] = work_part.Points.CreatePoint(
            x_scalar, y_scalar, zero_scalar,
            NXOpen.SmartObject.UpdateOption.WithinModeling,
        )
    for index, segment in enumerate(segments):
        first, second = points[index], points[index + 1]
        curve = work_part.Curves.CreateLine(
            point_objects[first["name"]], point_objects[second["name"]]
        )
        curve.SetName(segment["name"])
        curves.append(curve)
    include_builder = work_part.Sketches.CreateSketchIncludeGeometryBuilder(curves[0])
    for curve in curves:
        include_builder.ObjectsToInclude.Add(curve)
    include_builder.Commit()
    include_builder.Destroy()
    included = list(sketch.GetIncludedGeometry())
    if included:
        curves = included
    return curves


def create_revolve(work_part, sketch, curves):
    sketch.Deactivate(NXOpen.Sketch.ViewReorient.FalseValue, NXOpen.Sketch.UpdateLevel.Model)
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
    builder = work_part.Features.CreateRevolveBuilder(NXOpen.Features.Feature.Null)
    builder.Section = section
    point = work_part.Points.CreatePoint(NXOpen.Point3d(0.0, 0.0, 0.0))
    direction = work_part.Directions.CreateDirection(
        NXOpen.Point3d(0.0, 0.0, 0.0), NXOpen.Vector3d(1.0, 0.0, 0.0),
        NXOpen.SmartObject.UpdateOption.WithinModeling,
    )
    axis = work_part.Axes.CreateAxis(point, direction, NXOpen.SmartObject.UpdateOption.WithinModeling)
    axis.SetName("AXIS_STAP1_REVOLVE_X")
    builder.Axis = axis
    builder.Limits.StartExtend.Value.RightHandSide = "0"
    builder.Limits.EndExtend.Value.RightHandSide = "360"
    builder.BooleanOperation.Type = NXOpen.GeometricUtilities.BooleanOperation.BooleanType.Create
    feature = builder.CommitFeature()
    feature.SetName(STEP_NAME)
    set_attributes(feature, {
        "ELSTER_CAM_RULE_SCHEMA": CAM_RULE_SCHEMA,
        "ELSTER_CAM_FEATURE_ID": "STAP1_ROTATIONAL_BASE",
        "ELSTER_CAM_FEATURE_CLASS": "ROTATIONAL_BASE_BODY",
        "ELSTER_CAM_PROCESS": "TURNING_BASE_GEOMETRY",
        "ELSTER_CAM_STEP": STEP_NAME,
        "ELSTER_CAM_SIDE": "NA",
        "ELSTER_NATIVE_FEATURE_TYPE": "REVOLVE",
    })
    builder.Destroy()
    section.Destroy()
    sketch.Blank()
    return feature

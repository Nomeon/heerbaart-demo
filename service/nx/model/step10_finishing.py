"""Active builders extracted from elster_family/nx_step10_flange_finishing_journal.py."""

from __future__ import annotations

import math

import NXOpen
import NXOpen.Features
import NXOpen.GeometricUtilities
import NXOpen.UF

STEP_NAME = "STAP10_FLANGE_ROOTS_AND_RIMS"
STEP = STEP_NAME
UF = NXOpen.UF.UFSession.GetUFSession()

from .step2_flange_holes import verify_chamfers


def close(a, b):
    return math.isclose(a, b, abs_tol=0.002)


def value(part, name):
    return float(part.Expressions.FindObject(name).Value)


def tag(feature, identity, process):
    feature.SetName(identity)
    for key, val in {"ELSTER_CAM_RULE_SCHEMA": "ELSTER_CAM_RULES_V1", "ELSTER_CAM_FEATURE_ID": identity, "ELSTER_CAM_STEP": STEP, "ELSTER_CAM_PROCESS": process}.items():
        feature.SetAttribute(key, val)
    return feature


def edge_collector(part, edges):
    collector = part.ScCollectors.CreateCollector()
    collector.ReplaceRules([part.ScRuleFactory.CreateRuleEdgeDumb(edges)], False)
    return collector


def ring_edges(part, radius, x_values):
    result = []
    for edge in list(part.Bodies)[0].GetEdges():
        evaluator = UF.Eval.Initialize(edge.Tag)
        try:
            if not UF.Eval.IsArc(evaluator):
                continue
            arc = UF.Eval.AskArc(evaluator)
            if close(arc.Radius, radius) and close(arc.Center[1], 0) and close(arc.Center[2], 0) and any(close(arc.Center[0], x) for x in x_values):
                result.append(edge)
        finally:
            del evaluator
    return result


def build(part):
    flange_radius = value(part, "FA") / 2
    outer_x = 300 - value(part, "FR")
    root_x = outer_x - value(part, "FB")
    # Remove only the two temporary straight root transitions inherited from STAP1.
    # Heal extends the flange plane and body cylinder; the next feature adds R10.
    cones = []
    for face in list(part.Bodies)[0].GetFaces():
        kind, p, direction, box, radius, radial, normal = UF.Modeling.AskFaceData(face.Tag)
        if kind == 17 and close(abs(direction[0]), 1) and close(box[3]-box[0], (value(part, "DR") - 250) / 2):
            if close(max(abs(box[0]), abs(box[3])), root_x) and close(box[4]-box[1], value(part, "DR")):
                cones.append(face)
    if len(cones) != 2:
        raise RuntimeError(f"Exact twee scherpe flenswortel-overgangsvlakken verwacht; gevonden {len(cones)}")
    builder = part.Features.CreateDeleteFaceBuilder(NXOpen.Features.Feature.Null)
    try:
        builder.Type = NXOpen.Features.DeleteFaceBuilder.SelectTypes.Face
        builder.Heal = True
        builder.FaceCollector.ReplaceRules([part.ScRuleFactory.CreateRuleFaceDumb(cones)], False)
        cleanup = tag(builder.CommitFeature(), "STAP10_ROOT_TRANSITION_HEAL", "FLANGE_ROOT_PREPARATION")
    finally:
        builder.Destroy()
    edges = ring_edges(part, 125, [-root_x, root_x])
    if len(edges) != 2:
        raise RuntimeError(f"Twee rondlopende wortelranden verwacht; gevonden {len(edges)}")
    builder = part.Features.CreateEdgeBlendBuilder(NXOpen.Features.Feature.Null)
    try:
        builder.Tolerance = 0.001
        builder.AddChainset(edge_collector(part, edges), "STEP10_ROOT_RADIUS")
        blend = tag(builder.CommitFeature(), "STAP10_FLANGE_ROOT_R10", "FLANGE_ROOT_FINISHING")
    finally:
        builder.Destroy()
    edges = ring_edges(part, flange_radius, [-outer_x, -root_x, root_x, outer_x])
    if len(edges) != 4:
        raise RuntimeError(f"Vier buitenomtrekranden verwacht; gevonden {len(edges)}")
    builder = part.Features.CreateChamferBuilder(NXOpen.Features.Feature.Null)
    try:
        builder.Option = NXOpen.Features.ChamferBuilder.ChamferOption.OffsetAndAngle
        builder.FirstOffsetExp.SetFormula("STEP10_OUTER_CHAMFER")
        builder.AngleExp.SetFormula("STEP10_OUTER_CHAMFER_ANGLE")
        builder.SmartCollector = edge_collector(part, edges)
        chamfer = tag(builder.CommitFeature(), "STAP10_FLANGE_RIMS_C2_45", "FLANGE_RIM_CHAMFERING")
    finally:
        builder.Destroy()
    return [cleanup, blend, chamfer]


def verify(part, root_radius=10, offset=2):
    bodies = list(part.Bodies)
    if len(bodies) != 1 or not bodies[0].IsSolidBody:
        raise RuntimeError("STAP10 vereist een solid.")
    torus = []
    rims = []
    root_data = []
    flange_r = value(part, "FA") / 2
    root_x = 300 - value(part, "FR") - value(part, "FB")
    for face in bodies[0].GetFaces():
        kind, p, direction, box, radius, radial, normal = UF.Modeling.AskFaceData(face.Tag)
        if close(abs(box[3]-box[0]), root_radius):
            root_data.append([kind, list(p), list(box), radius, radial])
        if kind == 19 and close(radial, root_radius):
            if close(max(abs(box[0]), abs(box[3])), root_x) and close(box[3]-box[0], root_radius) and close(radius, 125+root_radius):
                torus.append({"bounding_box": list(box), "major_radius": radius, "minor_radius": radial})
        if kind == 17 and close(abs(direction[0]), 1) and close(box[3]-box[0], offset):
            if close(box[4]-box[1], 2*flange_r) and close(box[5]-box[2], 2*flange_r):
                if close(abs(radial), math.pi/4):
                    rims.append({"x_min": box[0], "x_max": box[3], "half_angle_rad": radial})
    if len(torus) != 2 or len(rims) != 4:
        raise RuntimeError(f"R10/C2 geometriecontrole mislukt: torussen={torus}, randen={rims}, root_data={root_data}")
    seeds = [f for f in part.Features if f.Name in ("LEFT_STAP2_FLANGE_GENERAL_HOLE", "RIGHT_STAP2_FLANGE_GENERAL_HOLE")]
    holes = verify_chamfers(part, seeds, value(part, "DS"))
    if len(seeds) != 2:
        raise RuntimeError("STAP2 Hole-features ontbreken.")
    return {"passed": True, "root_tori": torus, "outer_chamfer_faces": rims, "preserved_flange_hole_chamfers": holes}

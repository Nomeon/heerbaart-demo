"""Active builders extracted from elster_family/nx_step11_center_ports_journal.py."""

from __future__ import annotations

import math

import NXOpen
import NXOpen.Features
import NXOpen.GeometricUtilities
import NXOpen.UF

from .common import scalar_expression

STEP_NAME = "STAP11_CENTER_M12_AND_QUARTER_NPT"
STEP = STEP_NAME
UF = NXOpen.UF.UFSession.GetUFSession()

from .step10_finishing import verify as verify_finishing


def value(part, name):
    return float(part.Expressions.FindObject("STEP11_"+name).Value)


def point(part, port):
    scalar = scalar_expression
    return part.Points.CreatePoint(scalar(part,"STEP11_AXIAL_POSITION"),scalar(part,"STEP11_"+port+"_Y"),scalar(part,"STEP11_ENTRY_Z"), NXOpen.SmartObject.UpdateOption.WithinModeling)


def configure(part, builder, port):
    sign = 1 if port == "M12" else -1
    builder.Tolerance = 0.001
    builder.ProjectPointOntoTargetEnabled = False
    direction = part.Directions.CreateDirection(NXOpen.Point3d(0.0,0.0,0.0),NXOpen.Vector3d(0.0,-sign*math.sqrt(3)/2,-0.5),NXOpen.SmartObject.UpdateOption.WithinModeling)
    builder.ProjectionDirection.ProjectDirectionMethod = NXOpen.GeometricUtilities.ProjectionOptions.DirectionType.Vector
    builder.ProjectionDirection.ProjectVector = direction
    builder.BooleanOperation.Type = NXOpen.GeometricUtilities.BooleanOperation.BooleanType.Subtract
    builder.BooleanOperation.SetTargetBodies([list(part.Bodies)[0]])
    builder.HolePosition.AddSmartPoint(point(part,port),0.001)


def commit(builder, name, process):
    feature=builder.CommitFeature()
    feature.SetName(name)
    for key,val in {"ELSTER_CAM_RULE_SCHEMA":"ELSTER_CAM_RULES_V1","ELSTER_CAM_FEATURE_ID":name,"ELSTER_CAM_STEP":STEP,"ELSTER_CAM_PROCESS":process}.items():
        feature.SetAttribute(key,val)
    return feature


def create_d4(part):
    builder=part.Features.CreateHolePackageBuilder(NXOpen.Features.HolePackage.Null)
    try:
        builder.Type=NXOpen.Features.HolePackageBuilder.Types.GeneralHole
        builder.HoleSize=NXOpen.Features.HolePackageBuilder.Holesize.Custom
        builder.GeneralHoleForm=NXOpen.Features.HolePackageBuilder.HoleForms.Simple
        builder.HoleDepthLimitOption=NXOpen.Features.HolePackageBuilder.HoleDepthLimitOptions.UntilNext
        builder.GeneralSimpleHoleDiameter.SetFormula("STEP11_D4_DIAMETER")
        configure(part,builder,"NPT")
        return commit(builder,"STAP11_NPT_D4_CONTINUATION","RADIAL_D4_THROUGH_HOLE")
    finally:
        builder.Destroy()


def create_thread(part,port,entry):
    builder=part.Features.CreateHolePackageBuilder(NXOpen.Features.HolePackage.Null)
    try:
        builder.Type=NXOpen.Features.HolePackageBuilder.Types.ThreadedHole
        builder.ThreadStandard=entry["standard"]
        builder.ThreadSize=entry["size"]
        builder.RadialEngageOption=entry["radial_engage"]
        builder.ThreadLengthOption=NXOpen.Features.HolePackageBuilder.ThreadLengthOptions.Custom
        builder.RelateHoleDepthToThreadDepth=False
        builder.ThreadDepth.SetFormula("STEP11_"+port+"_THREAD_DEPTH")
        builder.ThreadedHoleDepth.SetFormula("STEP11_"+port+"_DRILL_DEPTH")
        builder.TapDrillDiameter.SetFormula("STEP11_"+port+"_TAP_DIAMETER")
        builder.ThreadedTipAngle.SetFormula("STEP11_"+port+"_TIP_ANGLE")
        builder.ThreadedStartChamferEnabled=True
        builder.ThreadedEndChamferEnabled=False
        for end in ("Start","End"):
            getattr(builder,"Threaded"+end+"ChamferDiameter").SetFormula("STEP11_"+port+"_"+end.upper()+"_CHAMFER")
            getattr(builder,"Threaded"+end+"ChamferAngle").SetFormula("STEP11_"+port+"_"+end.upper()+"_ANGLE")
        builder.ThreadedReliefEnabled=False
        builder.HoleDepthLimitOption=NXOpen.Features.HolePackageBuilder.HoleDepthLimitOptions.Value
        builder.DepthOption=NXOpen.Features.HolePackageBuilder.HoleDepthOptions.ToConeTip
        builder.ThreadRotation=NXOpen.Features.HolePackageBuilder.ThreadRotationOptions.Right
        builder.ThreadAtBothEnds=False
        configure(part,builder,port)
        feature=commit(builder,"STAP11_CENTER_"+port+"_THREADED_HOLE","RADIAL_HB_THREADED_PORT")
        feature.SetAttribute("ELSTER_CAM_THREAD_SIZE",entry["size"])
        return feature
    finally:
        builder.Destroy()


def verify(part,threads,d4,contract):
    readback={}
    for port,feature in threads.items():
        builder=part.Features.CreateHolePackageBuilder(feature)
        try:
            entry=contract["hb_table"]["entries"][port]
            if builder.ThreadSize != entry["size"] or builder.ThreadStandard != entry["standard"]:
                raise RuntimeError("Verkeerde HB-draad geselecteerd.")
            checks={"thread_depth_mm":(builder.ThreadDepth.Value,value(part,port+"_THREAD_DEPTH")),"drill_depth_mm":(builder.ThreadedHoleDepth.Value,value(part,port+"_DRILL_DEPTH")),"tap_drill_mm":(builder.TapDrillDiameter.Value,entry["tap_drill_diameter_mm"]),"tip_angle_deg":(builder.ThreadedTipAngle.Value,entry["hole_tip_angle_deg"]),"start_chamfer_mm":(builder.ThreadedStartChamferDiameter.Value,entry["start_chamfer_diameter_mm"]),"start_chamfer_angle_deg":(builder.ThreadedStartChamferAngle.Value,entry["start_chamfer_angle_deg"]),"end_chamfer_mm":(builder.ThreadedEndChamferDiameter.Value,entry["end_chamfer_diameter_mm"]),"end_chamfer_angle_deg":(builder.ThreadedEndChamferAngle.Value,entry["end_chamfer_angle_deg"])}
            if any(not math.isclose(float(a),b,abs_tol=0.001) for a,b in checks.values()) or not builder.ThreadedStartChamferEnabled or builder.ThreadedEndChamferEnabled:
                raise RuntimeError("HB-builder readback wijkt af: "+str(checks))
            readback[port]={"size":builder.ThreadSize,**{k:float(v[0]) for k,v in checks.items()},"entry_xyz":[value(part,"AXIAL_POSITION"),value(part,port+"_Y"),value(part,"ENTRY_Z")]}
        finally:
            builder.Destroy()
    builder=part.Features.CreateHolePackageBuilder(d4)
    try:
        if builder.HoleDepthLimitOption != NXOpen.Features.HolePackageBuilder.HoleDepthLimitOptions.UntilNext or not math.isclose(builder.GeneralSimpleHoleDiameter.Value,4,abs_tol=0.001):
            raise RuntimeError("D4 is niet Until Next / diameter 4.")
    finally:
        builder.Destroy()
    body=list(part.Bodies)[0]
    if len(list(part.Bodies)) != 1 or not body.IsSolidBody:
        raise RuntimeError("Een solid vereist.")
    states={}
    for name,sign,radius,expected in [("npt_channel",-1,100,2),("npt_bore_connection",-1,90.05,2),("opposite_wall_intact",-1,-100,1),("m12_blind_floor",1,109,1),("m12_hole",1,121,2)]:
        xyz=[value(part,"AXIAL_POSITION"),sign*math.sqrt(3)/2*radius,0.5*radius]
        state=UF.Modeling.AskPointContainment(xyz,body.Tag)
        states[name]=state
        if state != expected:
            raise RuntimeError(f"Geometriecontrole {name}: {state}, verwacht {expected}")
    preserved=verify_finishing(part)
    return {"passed":True,"thread_readback":readback,"d4_until_next":True,"point_containment":states,"preserved_step10_finishing":preserved}


def set_product_display(session, part):
    bodies = list(part.Bodies)
    modification = session.DisplayManager.NewDisplayModification()
    try:
        modification.ApplyToAllFaces = True
        modification.NewColor = 87
        modification.Apply(bodies)
    finally:
        modification.Dispose()
    if any(body.Color != 87 or any(face.Color != 87 for face in body.GetFaces()) for body in bodies):
        raise RuntimeError("Niet alle productvlakken hebben NX-kleur 87.")
    part.Views.WorkView.Orient(NXOpen.View.Canned.Trimetric, NXOpen.View.ScaleAdjustment.Fit)
    part.Views.WorkView.Fit()
    part.Views.Refresh()
    return {"color_index": 87, "all_body_faces_verified": True, "view": "TRIMETRIC"}

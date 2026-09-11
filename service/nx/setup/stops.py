"""Active workholding builders extracted from Setup_Generator/flow6/flow6_attach_holders.py."""

from pathlib import Path
import math
import re

import NXOpen
import NXOpen.Assemblies
import NXOpen.Positioning
import NXOpen.UF

from . import common as setup
from .product import _all_component_constraints


def _flow5_product_position_faces(machine_part, input_file, device_file):
    """Resolve the left flange stop, the jaw shoulders and the central flat."""
    session = NXOpen.Session.GetSession()
    uf = NXOpen.UF.UFSession.GetUFSession()
    product = setup.find_product_component(machine_part.ComponentAssembly.RootComponent, input_file.stem)

    def load_child(suffix):
        path = input_file.with_name(input_file.stem.removesuffix("_ASSY") + suffix + ".prt")
        part = next((p for p in session.Parts
                     if p.FullPath and Path(p.FullPath).resolve() == path.resolve()), None)
        if part is None:
            part = setup.open_base(session, path)
        session.Parts.EnsurePartsLoadedFully([part], True)
        child = setup.find_product_component(product, path.stem)
        opened = machine_part.ComponentAssembly.OpenComponents(
            NXOpen.Assemblies.ComponentAssemblyOpenOption.ComponentOnly, [child]
        )
        setup.dispose(opened[0])
        child.UpdateStructure([child], 2, True)
        return child, part

    def occurrence(component, face):
        found = component.FindOccurrence(face)
        if found is not None:
            return found
        identifier = face.JournalIdentifier
        feature = re.search(r"([A-Z_]+\(\d+\))", identifier)
        face_id = re.search(r"FACE \d+", identifier).group(0)
        if feature:
            return component.FindObject(f"PROTO#.Features|{feature.group(0)}|{face_id}")
        return component.FindObject(f"PROTO#.Features|REVOLVED(3)|{face_id}")

    blank, blank_part = load_child("_BLANK")
    diameter = setup.determine_spanning_diameter(blank_part)[0]
    body = next(b for b in blank_part.Bodies if b.Name == "BLANK_REVOLVE_OUTLINE_BODY")
    flange_faces = []
    axial_planar_faces = []
    for face in body.GetFaces():
        data = uf.Modeling.AskFaceData(face.Tag)
        if data[0] != 22 or abs(data[2][2]) <= 0.999999:
            continue
        # A chamfer can make the flat flange edge smaller than the largest
        # cylindrical stock diameter.  Select the largest actual planar
        # axial flange face and then the one furthest toward MAIN.
        radial_radius = max(
            abs(float(data[3][0])), abs(float(data[3][1])),
            abs(float(data[3][3])), abs(float(data[3][4])),
        )
        record = (float(data[1][2]), radial_radius, face)
        axial_planar_faces.append(record)
        if abs(radial_radius - diameter / 2) < 1e-5:
            flange_faces.append(record)
    if not flange_faces:
        if not axial_planar_faces:
            raise RuntimeError("Geen vlak axiaal aanslagvlak op de blank gevonden.")
        largest_planar_radius = max(record[1] for record in axial_planar_faces)
        flange_faces = [
            record for record in axial_planar_faces
            if abs(record[1] - largest_planar_radius) < 1e-5
        ]
        selected = min(flange_faces, key=lambda item: item[0])
        flange = occurrence(blank, selected[2])
        print(
            "Flow 5 aanslagvlak: exacte Øspandiameter-vlakrand ontbreekt door "
            f"randbewerking; grootste vlakke axiale flensrand gekozen, "
            f"radius={largest_planar_radius:.6f} mm, z={selected[0]:.6f} mm.",
            flush=True,
        )
    else:
        selected = min(flange_faces, key=lambda item: item[0])
        flange = occurrence(blank, selected[2])
        print(
            "Flow 5 aanslagvlak: vlakke flensrand op de spandiameter gekozen, "
            f"radius={diameter / 2:.6f} mm, z={selected[0]:.6f} mm.",
            flush=True,
        )

    cad, cad_part = load_child("_CAD4CAM")
    flats = []
    for body in cad_part.Bodies:
        for face in body.GetFaces():
            data = uf.Modeling.AskFaceData(face.Tag)
            if (data[0] == 22 and abs(data[2][2]) < 1e-6
                    and abs(data[1][2]) < 1e-5 and len(face.GetEdges()) == 8
                    and data[3][2] < 0 < data[3][5]):
                flats.append(face)
    if len(flats) != 1:
        raise RuntimeError(f"Verwacht één centraal vlak met vier gaten; gevonden: {len(flats)}.")
    top = occurrence(cad, flats[0])
    for path in (device_file, device_file.with_name(device_file.stem + "_PART.prt")):
        if not any(p.FullPath and Path(p.FullPath).resolve() == path.resolve() for p in session.Parts):
            setup.open_base(session, path)
    session.Parts.EnsurePartsLoadedFully([machine_part], True)
    jaws = []
    for component in machine_part.ComponentAssembly.RootComponent.GetChildren():
        if component.DisplayName != device_file.stem:
            continue
        jaw = setup.find_component_occurrence(component, device_file.stem + "_PART")
        # This unchanged library's broad shoulder is FACE 9 at local Z=36 mm.
        shoulder = jaw.FindObject("PROTO#.Features|UNPARAMETERIZED_FEATURE(1)|FACE 9")
        if uf.Modeling.AskFaceData(shoulder.Tag)[0] != 22:
            raise RuntimeError("Het klauwaanslagvlak is niet vlak.")
        jaws.append((component, shoulder))
    if len(jaws) != 3:
        raise RuntimeError(f"Verwacht drie klauwaanslagen; gevonden: {len(jaws)}.")
    return product, flange, top, jaws



def apply_product_stop_and_top(machine_part, input_file, device_file):
    """Seat the left flange with Touch and keep the central flat facing +X."""
    session = NXOpen.Session.GetSession()
    uf = NXOpen.UF.UFSession.GetUFSession()
    product, flange, top, jaws = _flow5_product_position_faces(machine_part, input_file, device_file)
    jaw, shoulder = jaws[0]
    datum = next(d for d in machine_part.Datums
                 if d.JournalIdentifier == "DATUM_CSYS(4) YZ plane")

    # Seed the requested half-turn, so parallel does not choose the underside.
    data = uf.Modeling.AskFaceData(top.Tag)
    angle = -math.atan2(data[2][1] * data[6], data[2][0] * data[6])
    rotation = setup.identity_matrix(NXOpen)
    rotation.Xx = rotation.Yy = math.cos(angle)
    rotation.Xy, rotation.Yx = -math.sin(angle), math.sin(angle)
    machine_part.ComponentAssembly.MoveComponent(product, NXOpen.Vector3d(0.0, 0.0, 0.0), rotation)

    for name, kind, moving_face, fixed_component, fixed_face, alignment in (
        ("FLOW5_AXIAL_TOUCH", NXOpen.Positioning.Constraint.Type.Touch,
         flange, jaw, shoulder, NXOpen.Positioning.Constraint.Alignment.InferAlign),
        ("FLOW5_TOP_PARALLEL", NXOpen.Positioning.Constraint.Type.Parallel,
         top, machine_part.ComponentAssembly.RootComponent, datum,
         NXOpen.Positioning.Constraint.Alignment.CoAlign),
    ):
        positioner, network = setup.begin_network(machine_part, NXOpen)
        constraint = positioner.CreateConstraint(True)
        constraint.SetName(name)
        constraint.ConstraintType = kind
        constraint.CreateConstraintReference(product, moving_face, False, False, False)
        fixed_ref = constraint.CreateConstraintReference(fixed_component, fixed_face, False, False, False)
        fixed_ref.SetFixHint(True)
        constraint.ConstraintAlignment = alignment
        network.AddMovableObject(product)
        network.SetMovingGroup([product])
        network.AddConstraint(constraint)
        network.Solve()
        network.ApplyToModel()
        fixed_ref.SetFixHint(False)
        setup.end_network(positioner, network, session)
        print(f"{name}: status={constraint.GetConstraintStatus()}", flush=True)
    validate_product_stop_and_top(machine_part, input_file, device_file)



def validate_product_stop_and_top(machine_part, input_file, device_file):
    uf = NXOpen.UF.UFSession.GetUFSession()
    product, flange, top, jaws = _flow5_product_position_faces(machine_part, input_file, device_file)
    flange_z = uf.Modeling.AskFaceData(flange.Tag)[1][2]
    gaps = [flange_z - uf.Modeling.AskFaceData(face.Tag)[1][2] for _, face in jaws]
    data = uf.Modeling.AskFaceData(top.Tag)
    normal = tuple(value * data[6] for value in data[2])
    if max(abs(gap) for gap in gaps) > 0.01 or normal[0] < 0.999999:
        raise RuntimeError(f"Eindpositie onjuist: aanslagafstanden={gaps}, vlaknormaal={normal}.")
    constraints = {c.Name: c for c, _ in _all_component_constraints(machine_part)}
    for name in ("FLOW5_AXIAL_TOUCH", "FLOW5_TOP_PARALLEL"):
        if name not in constraints or constraints[name].Suppressed:
            raise RuntimeError(f"Eindconstraint ontbreekt: {name}.")
    print(f"Productpositie gecontroleerd: Z={product.GetPosition()[0].Z:.6f}; "
          f"Touch-afstanden={gaps}; bovenvlaknormaal={normal}.", flush=True)

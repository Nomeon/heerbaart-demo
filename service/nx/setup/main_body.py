"""Active workholding builders extracted from Setup_Generator/flow6/flow6_attach_holders.py."""

import math

import NXOpen
import NXOpen.Features
import NXOpen.UF

from . import common as setup


def determine_blank_gripping_diameter(blank_part):
    """Find the outer blank diameter at the actual jaw-grip section.

    The blank contains a linked product body and several stepped axial
    sections.  The existing spanning-diameter routine remains the selector
    input for the device range.  For the jaw parameter, use only the named
    ``BLANK_REVOLVE_OUTLINE_BODY`` and its largest Z-axis cylinder: that is the
    outer stock surface which the teeth must enter, not the product body and
    not the smaller end section.
    """
    import NXOpen.UF

    body = next(
        (
            candidate for candidate in blank_part.Bodies
            if candidate.Name.upper() == "BLANK_REVOLVE_OUTLINE_BODY"
        ),
        None,
    )
    if body is None:
        raise RuntimeError(
            "De blank-gripmeting mist BLANK_REVOLVE_OUTLINE_BODY."
        )
    uf = NXOpen.UF.UFSession.GetUFSession()
    radii = []
    for face in body.GetFaces():
        face_type, _point, direction, _box, radius, _radial, _norm = (
            uf.Modeling.AskFaceData(face.Tag)
        )
        if (
            face_type == 16
            and abs(abs(float(direction[2])) - 1.0) <= 1e-6
            and float(radius) > 0.1
        ):
            radii.append(float(radius))
    if not radii:
        raise RuntimeError("Geen Z-cilinder gevonden voor de blank-gripdiameter.")
    grip_radius = max(radii)
    grip_diameter = 2.0 * grip_radius
    print(
        f"Flow 4 blank-gripmeting: grootste buitencilinder van de blank = "
        f"Ø{grip_diameter:.6f} mm (radius {grip_radius:.6f} mm).",
        flush=True,
    )
    return grip_diameter



def _flow6_main_outside_point_target(machine_part, delta_x, delta_z):
    """Return MAIN_OUTSIDE and its world target for local MAIN offsets."""
    point_feature = machine_part.Features.FindObject("POINT(5)")
    if point_feature is None or str(point_feature.Name).upper() != "MAIN_OUTSIDE":
        raise RuntimeError(
            "Flow 6 verwacht Point (5) MAIN_OUTSIDE; het bestaande punt ontbreekt."
        )
    parents = list(point_feature.GetParents())
    main_csys = next(
        (
            parent for parent in parents
            if str(getattr(parent, "Name", "")).upper() == "MAIN"
            and str(getattr(parent, "FeatureType", "")).upper() == "DATUM_CSYS"
        ),
        None,
    )
    if main_csys is None:
        raise RuntimeError(
            "Point (5) MAIN_OUTSIDE heeft geen bestaand MAIN-datumsysteem als ouder."
        )
    cartesian = next(
        (
            entity for entity in main_csys.GetEntities()
            if type(entity).__name__ == "CartesianCoordinateSystem"
        ),
        None,
    )
    if cartesian is None:
        raise RuntimeError("Het MAIN-datumsysteem bevat geen cartesisch coördinatensysteem.")
    origin = cartesian.Origin
    matrix = cartesian.Orientation.Element
    local = (float(delta_x), 0.0, float(delta_z))
    target = NXOpen.Point3d(
        float(origin.X) + matrix.Xx * local[0] + matrix.Xy * local[1] + matrix.Xz * local[2],
        float(origin.Y) + matrix.Yx * local[0] + matrix.Yy * local[1] + matrix.Yz * local[2],
        float(origin.Z) + matrix.Zx * local[0] + matrix.Zy * local[1] + matrix.Zz * local[2],
    )
    return point_feature, target



def _flow6_main_outside_point_delta(machine_part, point_feature):
    """Read the local MAIN_OUTSIDE offset from the current datum system."""
    parents = list(point_feature.GetParents())
    main_csys = next(
        (
            parent for parent in parents
            if str(getattr(parent, "Name", "")).upper() == "MAIN"
            and str(getattr(parent, "FeatureType", "")).upper() == "DATUM_CSYS"
        ),
        None,
    )
    if main_csys is None:
        raise RuntimeError("MAIN_OUTSIDE heeft geen MAIN-datumsysteem als ouder.")
    cartesian = next(
        entity for entity in main_csys.GetEntities()
        if type(entity).__name__ == "CartesianCoordinateSystem"
    )
    origin = cartesian.Origin
    matrix = cartesian.Orientation.Element
    inverse = (
        (matrix.Xx, matrix.Yx, matrix.Zx),
        (matrix.Xy, matrix.Yy, matrix.Zy),
        (matrix.Xz, matrix.Yz, matrix.Zz),
    )
    point = list(point_feature.GetEntities())
    if len(point) != 1:
        raise RuntimeError("Point (5) MAIN_OUTSIDE bevat niet exact één punt-entity.")
    world = point[0].Coordinates
    delta = (
        float(world.X) - float(origin.X),
        float(world.Y) - float(origin.Y),
        float(world.Z) - float(origin.Z),
    )
    return (
        inverse[0][0] * delta[0] + inverse[0][1] * delta[1] + inverse[0][2] * delta[2],
        inverse[1][0] * delta[0] + inverse[1][1] * delta[1] + inverse[1][2] * delta[2],
        inverse[2][0] * delta[0] + inverse[2][1] * delta[1] + inverse[2][2] * delta[2],
    )



def apply_flow6_main_outside_and_linked_body(
    session, machine_part, input_file, blank_diameter
):
    """Set MAIN_OUTSIDE offsets and relink MAIN Linked Body to CAD4CAM."""
    delta_x = float(blank_diameter) / 2.0 + 50.0
    delta_z = 10.0
    point_feature, target = _flow6_main_outside_point_target(
        machine_part, delta_x, delta_z
    )
    x_expression = machine_part.Expressions.FindObject("p4_xdelta")
    z_expression = machine_part.Expressions.FindObject("p6_zdelta")
    if x_expression is None or z_expression is None:
        raise RuntimeError(
            "MAIN_OUTSIDE mist de bestaande offsetexpressies p4_xdelta/p6_zdelta."
        )
    # These are the Delta X and Delta Z fields of Point (5) in NX.  Editing
    # the expressions keeps the existing MAIN datum-system parent intact;
    # replacing the point object would break that associativity after reopen.
    setup.require_setup_owned(x_expression, machine_part)
    setup.require_setup_owned(z_expression, machine_part)
    x_expression.RightHandSide = f"{delta_x:.9f}"
    z_expression.RightHandSide = f"{delta_z:.9f}"
    session.UpdateManager.DoUpdate(session.NewestVisibleUndoMark)
    actual_point = list(point_feature.GetEntities())
    if len(actual_point) != 1:
        raise RuntimeError("Point (5) MAIN_OUTSIDE is na de wijziging niet meer geldig.")
    actual = actual_point[0].Coordinates
    point_error = math.sqrt(sum(
        (float(getattr(actual, axis)) - float(getattr(target, axis))) ** 2
        for axis in ("X", "Y", "Z")
    ))
    if point_error > 1.0e-5:
        raise RuntimeError(
            "MAIN_OUTSIDE kon niet op de berekende lokale offset worden gezet; "
            f"fout={point_error:.9f} mm."
        )

    root = machine_part.ComponentAssembly.RootComponent
    product = setup.find_product_component(root, input_file.stem)
    cad_stem = input_file.stem.removesuffix("_ASSY") + "_CAD4CAM"
    cad_component = setup.find_product_component(product, cad_stem)
    if cad_component is None:
        raise RuntimeError(f"CAD4CAM-occurrence ontbreekt: {cad_stem}.")
    cad_component.UpdateStructure([cad_component], 2, True)
    cad_path = input_file.with_name(cad_stem + ".prt")
    cad_part = setup.open_base(session, cad_path)
    session.Parts.EnsurePartsLoadedFully([cad_part], True)
    cad_body = next(
        (
            body for body in cad_part.Bodies
            if str(body.Name).upper() == "CAD4CAM_BODY"
        ),
        None,
    )
    if cad_body is None:
        raise RuntimeError("CAD4CAM_BODY ontbreekt in de CAD4CAM-bronpart.")

    linked_body = machine_part.Features.FindObject("LINKED_BODY(10)")
    if linked_body is None or str(linked_body.Name).upper() != "MAIN":
        raise RuntimeError(
            "Flow 6 verwacht Linked Body (10) MAIN; het bestaande feature ontbreekt."
        )
    setup.require_setup_owned(linked_body, machine_part)
    uf = NXOpen.UF.UFSession.GetUFSession()
    xform_result = uf.So.CreateXformAssyCtxt(
        machine_part.Views.WorkView.Tag,
        cad_component.Tag,
        0,
    )
    assembly_xform = xform_result[-1] if isinstance(xform_result, tuple) else xform_result
    if not uf.So.IsAssyCtxtXform(assembly_xform):
        raise RuntimeError("CAD4CAM gaf geen geldige assembly-contexttransform voor MAIN.")
    uf.Wave.SetLinkData(linked_body.Tag, cad_body.Tag, assembly_xform, False)
    session.UpdateManager.DoUpdate(session.NewestVisibleUndoMark)

    result_bodies = list(linked_body.GetBodies())
    if len(result_bodies) != 1:
        raise RuntimeError(
            "Linked Body (10) MAIN levert niet exact één resultaat-body op: "
            f"{len(result_bodies)}."
        )
    display_modification = session.DisplayManager.NewDisplayModification()
    try:
        display_modification.ApplyToAllFaces = True
        display_modification.ApplyToOwningParts = False
        display_modification.NewColor = 145
        display_modification.Apply(result_bodies)
    finally:
        display_modification.Dispose()
    session.UpdateManager.DoUpdate(session.NewestVisibleUndoMark)

    probe = machine_part.Features.CreateExtractFaceBuilder(linked_body)
    try:
        wave_info = str(probe.GetWaveLinkInformation()[0])
    finally:
        probe.Destroy()
    if "_CAD4CAM" not in wave_info.upper() or "LINKED BODY(1)" not in wave_info.upper():
        raise RuntimeError(
            "Linked Body (10) MAIN verwijst niet naar CAD4CAM: "
            f"{wave_info}"
        )
    color = int(result_bodies[0].Color)
    if color != 145:
        raise RuntimeError(
            f"Linked Body (10) MAIN heeft kleur-ID {color}; verwacht 145."
        )
    print(
        "Flow 6 MAIN_OUTSIDE en Linked Body MAIN ingesteld: "
        f"blankdiameter={blank_diameter:.6f} mm; "
        f"Delta X={delta_x:.6f} mm; Delta Z={delta_z:.6f} mm; "
        f"kleur-ID={color}; bron=CAD4CAM.",
        flush=True,
    )
    return delta_x, delta_z



def validate_flow6_main_outside_and_linked_body(
    session, machine_part, input_file, blank_diameter
):
    """Validate MAIN_OUTSIDE and Linked Body MAIN after save/reopen."""
    delta_x = float(blank_diameter) / 2.0 + 50.0
    delta_z = 10.0
    point_feature, target = _flow6_main_outside_point_target(
        machine_part, delta_x, delta_z
    )
    actual_point = list(point_feature.GetEntities())
    if len(actual_point) != 1:
        raise RuntimeError("Flow 6 reopencontrole: MAIN_OUTSIDE bevat niet één punt.")
    actual = actual_point[0].Coordinates
    point_error = math.sqrt(sum(
        (float(getattr(actual, axis)) - float(getattr(target, axis))) ** 2
        for axis in ("X", "Y", "Z")
    ))
    local_delta = _flow6_main_outside_point_delta(machine_part, point_feature)
    if point_error > 1.0e-5 or abs(local_delta[0] - delta_x) > 1.0e-5 or abs(local_delta[2] - delta_z) > 1.0e-5:
        raise RuntimeError(
            "Flow 6 reopencontrole: MAIN_OUTSIDE-offset is onjuist; "
            f"Delta=({local_delta[0]:.9f}, {local_delta[1]:.9f}, {local_delta[2]:.9f})."
        )
    linked_body = machine_part.Features.FindObject("LINKED_BODY(10)")
    if linked_body is None or str(linked_body.Name).upper() != "MAIN":
        raise RuntimeError("Flow 6 reopencontrole: Linked Body (10) MAIN ontbreekt.")
    probe = machine_part.Features.CreateExtractFaceBuilder(linked_body)
    try:
        wave_info = str(probe.GetWaveLinkInformation()[0])
    finally:
        probe.Destroy()
    result_bodies = list(linked_body.GetBodies())
    colors = [int(body.Color) for body in result_bodies]
    if "_CAD4CAM" not in wave_info.upper() or "LINKED BODY(1)" not in wave_info.upper():
        raise RuntimeError(
            "Flow 6 reopencontrole: Linked Body MAIN heeft geen CAD4CAM-bron."
        )
    if colors != [145]:
        raise RuntimeError(
            f"Flow 6 reopencontrole: Linked Body MAIN kleur={colors}; verwacht [145]."
        )
    print(
        "Flow 6 reopencontrole MAIN_OUTSIDE/Linked Body OK: "
        f"Delta X={local_delta[0]:.6f} mm; Delta Z={local_delta[2]:.6f} mm; "
        "bron=CAD4CAM; kleur-ID=145.",
        flush=True,
    )

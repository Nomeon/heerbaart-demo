"""Active workholding builders extracted from Setup_Generator/flow6/flow6_attach_holders.py."""

import math
import re

import NXOpen
import NXOpen.Assemblies
import NXOpen.Features
import NXOpen.UF

from . import common as setup


def _point_tuple(point):
    return (float(point.X), float(point.Y), float(point.Z))



def _dot_vector(left, right):
    return sum(float(a) * float(b) for a, b in zip(left, right))



def _unit_vector(vector):
    length = math.sqrt(_dot_vector(vector, vector))
    if length <= 1.0e-12:
        raise RuntimeError("CAD4CAM-as kan niet worden bepaald: nulrichting.")
    return tuple(float(value) / length for value in vector)



def _transform_local_point(values, origin, matrix):
    x, y, z = (float(value) for value in values)
    return (
        float(origin.X) + matrix.Xx * x + matrix.Xy * y + matrix.Xz * z,
        float(origin.Y) + matrix.Yx * x + matrix.Yy * y + matrix.Yz * z,
        float(origin.Z) + matrix.Zx * x + matrix.Zy * y + matrix.Zz * z,
    )



def _transform_local_vector(values, matrix):
    x, y, z = (float(value) for value in values)
    return (
        matrix.Xx * x + matrix.Xy * y + matrix.Xz * z,
        matrix.Yx * x + matrix.Yy * y + matrix.Yz * z,
        matrix.Zx * x + matrix.Zy * y + matrix.Zz * z,
    )



def _resolve_flow6_main_edge_target(machine_part, input_file):
    """Select the largest circular contour on the farthest axial CAD4CAM face.

    This is the active Flow 6 rule: the far-plane selection precedes the
    radius tie-break, without a model-specific diameter or edge identifier.
    """
    session = NXOpen.Session.GetSession()
    uf = NXOpen.UF.UFSession.GetUFSession()
    root = machine_part.ComponentAssembly.RootComponent
    product = setup.find_product_component(root, input_file.stem)
    cad_stem = input_file.stem.removesuffix("_ASSY") + "_CAD4CAM"
    cad_component = setup.find_product_component(product, cad_stem)

    cad_path = input_file.with_name(cad_stem + ".prt")
    cad_part = setup.open_base(session, cad_path)
    session.Parts.EnsurePartsLoadedFully([cad_part], True)
    opened = machine_part.ComponentAssembly.OpenComponents(
        NXOpen.Assemblies.ComponentAssemblyOpenOption.ComponentOnly,
        [cad_component],
    )
    setup.dispose(opened[0] if isinstance(opened, tuple) else opened)
    cad_component.UpdateStructure([cad_component], 2, True)
    cad_origin, cad_matrix = cad_component.GetPosition()

    main_chuck = root.FindObject("COMPONENT SMW_KNCS-N_400-128-A8_OUT 2")
    if main_chuck is None:
        raise RuntimeError("MAIN_CHUCK/spil 1-occurrence ontbreekt in de setup.")
    spindle1_center = _point_tuple(main_chuck.GetPosition()[0])

    linked = machine_part.Features.FindObject("LINKED_CURVE(2)")
    entities = list(linked.GetEntities())
    arcs = [entity for entity in entities if hasattr(entity, "CenterPoint")]
    if len(arcs) != 1:
        raise RuntimeError(
            "Linked Composite Curve (2) MAIN bevat niet exact één boog: "
            f"{len(arcs)}."
        )
    arc = arcs[0]

    bodies = [
        body for body in cad_part.Bodies
        if str(getattr(body, "Name", "")).upper() == "CAD4CAM_BODY"
    ] or list(cad_part.Bodies)
    if not bodies:
        raise RuntimeError("CAD4CAM bevat geen solid body.")

    # The bounding box is used only for the axial viewing direction.  The
    # target itself is always obtained from a real circular B-rep edge.
    minima = [float("inf"), float("inf"), float("inf")]
    maxima = [float("-inf"), float("-inf"), float("-inf")]
    for body in bodies:
        for face in body.GetFaces():
            data = uf.Modeling.AskFaceData(face.Tag)
            if len(data) < 4 or len(data[3]) < 6:
                continue
            raw_box = tuple(float(value) for value in data[3])
            local_min = [min(raw_box[index], raw_box[index + 3]) for index in range(3)]
            local_max = [max(raw_box[index], raw_box[index + 3]) for index in range(3)]
            for corner in (
                (x, y, z)
                for x in (local_min[0], local_max[0])
                for y in (local_min[1], local_max[1])
                for z in (local_min[2], local_max[2])
            ):
                point = _transform_local_point(corner, cad_origin, cad_matrix)
                for axis in range(3):
                    minima[axis] = min(minima[axis], point[axis])
                    maxima[axis] = max(maxima[axis], point[axis])
    if not all(math.isfinite(value) for value in minima + maxima):
        raise RuntimeError("CAD4CAM-bounding box kon niet worden bepaald.")
    cad_center = tuple((minima[axis] + maxima[axis]) / 2.0 for axis in range(3))
    direction = _unit_vector(tuple(cad_center[index] - spindle1_center[index]
                                   for index in range(3)))

    seen_tags = set()
    candidates = []
    candidate_by_tag = {}
    for body in bodies:
        for face in body.GetFaces():
            for edge in face.GetEdges():
                if edge.Tag in seen_tags:
                    continue
                seen_tags.add(edge.Tag)
                if str(getattr(edge, "SolidEdgeType", "")) != "2":
                    continue
                vertices = list(edge.GetVertices())
                if len(vertices) != 2:
                    continue
                first, second = vertices
                seam = math.sqrt(
                    (float(first.X) - float(second.X)) ** 2
                    + (float(first.Y) - float(second.Y)) ** 2
                    + (float(first.Z) - float(second.Z)) ** 2
                )
                if seam > 1.0e-4:
                    continue
                try:
                    radius = float(edge.GetLength()) / (2.0 * math.pi)
                    locations = list(edge.GetLocations())
                except Exception:
                    continue
                if radius <= 1.0e-6 or not locations:
                    continue
                local_center = _point_tuple(locations[0].Location)
                center = _transform_local_point(local_center, cad_origin, cad_matrix)
                axial = _dot_vector(
                    tuple(center[index] - spindle1_center[index] for index in range(3)),
                    direction,
                )
                candidate = {
                    "edge": edge,
                    "face": face,
                    "radius": radius,
                    "center": center,
                    "axial": axial,
                }
                candidates.append(candidate)
                candidate_by_tag[edge.Tag] = candidate
    if not candidates:
        raise RuntimeError("CAD4CAM bevat geen volledige circulaire B-rep-edge.")

    # Reject off-axis circles (bolt holes, pockets, etc.) first.
    axial_tolerance = 1.0e-6
    central = []
    for item in candidates:
        delta = tuple(item["center"][index] - spindle1_center[index]
                      for index in range(3))
        axial_component = tuple(direction[index] * item["axial"]
                                for index in range(3))
        transverse = math.sqrt(sum(
            (delta[index] - axial_component[index]) ** 2
            for index in range(3)
        ))
        if transverse <= axial_tolerance:
            item["transverse"] = transverse
            central.append(item)
    pool = central or candidates

    # Determine the plane farthest from the MAIN chuck.  The hard circular
    # edge must come from that plane; a larger contour on a nearer flange is
    # not a valid substitute.
    axial_faces = []
    for body in bodies:
        for face in body.GetFaces():
            try:
                data = uf.Modeling.AskFaceData(face.Tag)
            except Exception:
                continue
            if len(data) < 4 or int(data[0]) != 22:
                continue
            local_normal = tuple(float(value) for value in data[2])
            normal = _transform_local_vector(local_normal, cad_matrix)
            if abs(_dot_vector(normal, direction)) < 0.999:
                continue
            point = _transform_local_point(data[1], cad_origin, cad_matrix)
            face_edges = [
                candidate_by_tag[edge.Tag]
                for edge in face.GetEdges()
                if edge.Tag in candidate_by_tag
                and candidate_by_tag[edge.Tag] in pool
            ]
            if not face_edges:
                continue
            axial = _dot_vector(
                tuple(point[index] - spindle1_center[index]
                      for index in range(3)),
                direction,
            )
            axial_faces.append((axial, face, face_edges))
    if not axial_faces:
        raise RuntimeError(
            "CAD4CAM bevat geen axiaal georiënteerd vlak met een circulaire rand."
        )

    _far_axial, far_face, face_edges = max(
        axial_faces,
        key=lambda item: item[0],
    )
    # Select the largest central hard contour on the already selected far
    # plane.  The plane choice is primary; radius is only a tie-breaker.
    ordered_face_edges = sorted(
        face_edges, key=lambda item: item["radius"], reverse=True
    )
    if len(ordered_face_edges) < 1:
        raise RuntimeError(
            "Het verste CAD4CAM-vlak bevat geen harde circulaire rand."
        )
    target = ordered_face_edges[0]
    prototype_edge = target["edge"]
    edge_id = re.search(r"(EDGE \* \d+ \* \d+)",
                        str(prototype_edge.JournalIdentifier))
    feature_id = re.search(r"([A-Z_]+\(\d+\))",
                           str(prototype_edge.JournalIdentifier))
    if edge_id is None or feature_id is None:
        raise RuntimeError(
            "CAD4CAM-edge heeft geen bruikbare feature/edge-identificatie."
        )
    occurrence_path = (
        f"PROTO#.Features|{feature_id.group(1)}|{edge_id.group(1)}"
    )
    try:
        occurrence_edge = cad_component.FindObject(occurrence_path)
    except Exception:
        occurrence_edge = None
    if occurrence_edge is None:
        try:
            occurrence_edge = cad_component.FindOccurrence(prototype_edge)
        except Exception:
            occurrence_edge = None
    if occurrence_edge is None or not bool(getattr(occurrence_edge, "IsOccurrence", False)):
        raise RuntimeError(
            "De CAD4CAM-edge kon niet als assembly-occurrence worden gevonden: "
            f"{occurrence_path}."
        )
    return {
        "arc": arc,
        "linked": linked,
        "cad_component": cad_component,
        "cad_part": cad_part,
        "edge": occurrence_edge,
        "prototype_edge": prototype_edge,
        "target": target["center"],
        "target_local": _point_tuple(target["edge"].GetLocations()[0].Location),
        "cad_origin": cad_origin,
        "cad_matrix": cad_matrix,
        "target_radius": target["radius"],
        "direction": direction,
        "axial": target["axial"],
        "target_face": far_face,
    }



def move_flow6_main_curve_to_cad4cam_far_face(machine_part, input_file):
    """Relink MAIN to a hard CAD4CAM edge in assembly context.

    UF_WAVE receives the prototype edge and an associative assembly-context
    transform.  No curve geometry is transferred or repositioned.
    """
    session = NXOpen.Session.GetSession()
    uf = NXOpen.UF.UFSession.GetUFSession()
    info = _resolve_flow6_main_edge_target(machine_part, input_file)
    setup.require_setup_owned(info["linked"], machine_part)
    object_in_part = machine_part.Views.WorkView.Tag
    try:
        xform_result = uf.So.CreateXformAssyCtxt(
            object_in_part,
            info["cad_component"].Tag,
            0,
        )
        assembly_xform = xform_result[-1] if isinstance(xform_result, tuple) else xform_result
        if not uf.So.IsAssyCtxtXform(assembly_xform):
            raise RuntimeError("ongeldige assembly-contexttransform")
        # UF_WAVE deliberately receives the prototype edge.  The occurrence
        # transform is supplied separately, exactly as the manual WAVE
        # Geometry Linker does for an edge selected in CAD4CAM.
        uf.Wave.SetLinkData(
            info["linked"].Tag,
            info["prototype_edge"].Tag,
            assembly_xform,
            False,
        )
    except Exception as error:
        raise RuntimeError(
            "Flow 6 kon MAIN niet aan de geselecteerde harde CAD4CAM-edge "
            f"koppelen: {error}"
        ) from error
    session.UpdateManager.DoUpdate(session.NewestVisibleUndoMark)
    actual = _point_tuple(info["arc"].CenterPoint)
    error = math.sqrt(sum(
        (actual[index] - info["target"][index]) ** 2
        for index in range(3)
    ))
    radius_error = abs(float(info["arc"].Radius) - float(info["target_radius"]))
    if error > 1.0e-5 or radius_error > 1.0e-5:
        raise RuntimeError(
            "MAIN-curve kon niet aan de harde CAD4CAM-edge worden gekoppeld; "
            f"assemblyfout={error:.9f} mm, "
            f"radiusfout={radius_error:.9f} mm."
        )
    print(
        "Flow 6 MAIN gekoppeld aan harde, dynamische CAD4CAM-edge: "
        f"{info['edge'].JournalIdentifier}, radius={info['target_radius']:.6f} mm, "
        f"assemblycentrum=({actual[0]:.6f}, {actual[1]:.6f}, {actual[2]:.6f}), "
        f"axiaal={info['axial']:.6f} mm.",
        flush=True,
    )
    return info["target"]



def validate_flow6_main_curve(machine_part, input_file):
    """Verify the edge exchange and attached MAIN datum after reopen."""
    info = _resolve_flow6_main_edge_target(machine_part, input_file)
    actual = _point_tuple(info["arc"].CenterPoint)
    target = info["target"]
    error = math.sqrt(sum((actual[index] - target[index]) ** 2 for index in range(3)))
    radius_error = abs(float(info["arc"].Radius) - float(info["target_radius"]))
    if error > 1.0e-5 or radius_error > 1.0e-5:
        raise RuntimeError(
            "Flow 6 reopencontrole: MAIN is niet de uiterste CAD4CAM-cirkel; "
            f"assemblyfout={error:.9f} mm, "
            f"radiusfout={radius_error:.9f} mm."
        )
    datum_children = [
        child for child in info["linked"].GetChildren()
        if type(child).__name__ == "DatumCsys"
    ]
    if len(datum_children) != 1:
        raise RuntimeError(
            "Flow 6 reopencontrole: MAIN heeft niet exact één gekoppeld nulpunt; "
            f"gevonden={len(datum_children)}."
        )
    datum_location = _point_tuple(datum_children[0].Location)
    datum_error_direct = math.sqrt(sum(
        (datum_location[index] - target[index]) ** 2 for index in range(3)
    ))
    if datum_error_direct > 1.0e-5:
        raise RuntimeError(
            "Flow 6 reopencontrole: MAIN-nulpunt staat niet op de geselecteerde "
            f"CAD4CAM-cirkel; fout={datum_error_direct:.9f} mm."
        )
    probe = machine_part.Features.CreateCompositeCurveBuilder(info["linked"])
    try:
        wave_info = probe.GetWaveLinkInformation()
    finally:
        probe.Destroy()
    wave_text = str(wave_info[0]) if isinstance(wave_info, tuple) else str(wave_info)
    if "CAD4CAM" not in wave_text.upper() or "WAVE LINK" not in wave_text.upper():
        raise RuntimeError(
            "Flow 6 reopencontrole: MAIN heeft geen geldige CAD4CAM-WAVE-bron; "
            f"informatie={wave_text}"
        )
    print(
        "Flow 6 reopencontrole MAIN OK: echte CAD4CAM-cirkel="
        f"{info['edge'].JournalIdentifier}, radius={info['target_radius']:.6f} mm, "
        f"assemblycentrum=({actual[0]:.6f}, {actual[1]:.6f}, {actual[2]:.6f}), "
        f"nulpuntfout={datum_error_direct:.9f} mm.",
        flush=True,
    )



def position_flow6_main_curve_after_product_setup(machine_part, input_file):
    """Update the position-dependent WAVE link after Flow 5's solve."""
    session = NXOpen.Session.GetSession()
    session.UpdateManager.DoUpdate(session.NewestVisibleUndoMark)
    info = _resolve_flow6_main_edge_target(machine_part, input_file)
    actual = _point_tuple(info["arc"].CenterPoint)
    error = math.sqrt(sum(
        (actual[index] - info["target"][index]) ** 2
        for index in range(3)
    ))
    if error > 1.0e-5:
        raise RuntimeError(
            "De positie-afhankelijke WAVE-link volgt CAD4CAM niet na Flow 5; "
            f"fout={error:.9f} mm."
        )
    print(
        "Flow 6 MAIN volgt de harde CAD4CAM-edge na Flow 5: "
        f"assemblycentrum=({actual[0]:.6f}, {actual[1]:.6f}, {actual[2]:.6f}), "
        f"radius={info['target_radius']:.6f} mm.",
        flush=True,
    )

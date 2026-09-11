"""Active workholding builders extracted from Setup_Generator/flow6/flow6_attach_holders.py."""

from pathlib import Path
import math

import NXOpen
import NXOpen.Assemblies
import NXOpen.Positioning
import NXOpen.UF

from . import common as setup
from .holders import snapshot_constraint_states


def apply_journal_blank_touch_constraint(session, machine_part, input_file, device_root):
    """Keep the journal's axis Touch, using the current blank's central bore."""
    root = machine_part.ComponentAssembly.RootComponent
    product = setup.find_product_component(root, input_file.stem)
    blank_stem = input_file.stem.removesuffix("_ASSY") + "_BLANK"
    blank = setup.find_product_component(product, blank_stem)

    chuck_outer = root.FindObject(
        "COMPONENT SMW_KNCS-N_400-128-A8_OUT 2"
    )
    chuck_assy = chuck_outer.FindObject(
        "COMPONENT SMW_KNCS-N_400-128-A8_out_assy 1"
    )
    chuck = chuck_assy.FindObject(
        "COMPONENT KNCS-N_400-128_chuck 1"
    )
    opened = machine_part.ComponentAssembly.OpenComponents(
        NXOpen.Assemblies.ComponentAssemblyOpenOption.ComponentOnly,
        [chuck],
    )
    setup.dispose(opened[0] if isinstance(opened, tuple) else opened)
    try:
        chuck_part = setup.open_base(
            session,
            device_root / "__Components" / "KNCS-N_400-128_chuck.prt",
        )
    except Exception as error:
        if "File already exists" not in str(error):
            raise
        chuck_part = None
    if chuck_part is not None:
        session.Parts.EnsurePartsLoadedFully([chuck_part], True)
    chuck_face_2142 = setup.find_face(chuck, [
        "PROTO#.Features|UNPARAMETERIZED_FEATURE(0)|FACE 2142 "
        "{(21.8892891728428,60.1403277302982,84.85) "
        "UNPARAMETERIZED_FEATURE(0)}"
    ])

    # The journal's FACE 20 was the central inner cylinder, not an end face.
    # Resolve that geometry on the current blank instead of old face numbers.
    blank_path = input_file.with_name(blank_stem + ".prt").resolve()
    blank_part = next(
        part for part in session.Parts
        if part.FullPath and Path(part.FullPath).resolve() == blank_path
    )
    session.Parts.EnsurePartsLoadedFully([blank_part], True)
    body = next(
        body for body in blank_part.Bodies
        if body.Name.upper() == "BLANK_REVOLVE_OUTLINE_BODY"
    )
    uf = NXOpen.UF.UFSession.GetUFSession()
    bore_faces = []
    for face in body.GetFaces():
        kind, point, direction, _box, radius, _radial, normal = (
            uf.Modeling.AskFaceData(face.Tag)
        )
        if (
            kind == 16 and normal == -1 and radius > 0.1
            and abs(abs(float(direction[2])) - 1.0) < 1e-6
            and math.hypot(float(point[0]), float(point[1])) < 1e-6
        ):
            bore_faces.append(face)
    if len(bore_faces) != 1:
        raise RuntimeError(
            f"Flow 5 verwacht precies een centrale cilindrische binnenboring; "
            f"gevonden: {len(bore_faces)}."
        )
    blank_face = blank.FindOccurrence(bore_faces[0])
    if blank_face is None:
        raise RuntimeError("Flow 5 kan de binnenboring niet aan de blank-occurrence koppelen.")
    blank_help = setup.face_help_point(blank_face, NXOpen)
    chuck_help = setup.face_help_point(chuck_face_2142, NXOpen)

    before = snapshot_constraint_states(machine_part)
    positioner, network = setup.begin_network(machine_part, NXOpen)
    helper_lines = []
    constraint = None
    try:
        # Only the two axes used by the persistent constraint are needed.
        for face in (chuck_face_2142, blank_face):
            helper_lines.append(machine_part.Lines.CreateFaceAxis(
                face, NXOpen.SmartObject.UpdateOption.AfterModeling
            ))

        constraint = positioner.CreateConstraint(True)
        constraint.SetName("ELSTER_AXIS_TOUCH")
        constraint.ConstraintType = NXOpen.Positioning.Constraint.Type.Touch
        chuck_ref = constraint.CreateConstraintReference(
            chuck, chuck_face_2142, True, False, False
        )
        chuck_ref.HelpPoint = chuck_help
        blank_ref = constraint.CreateConstraintReference(
            product, blank_face, True, False, False
        )
        blank_ref.HelpPoint = blank_help
        blank_ref.SetFixHint(True)
        constraint.ConstraintAlignment = (
            NXOpen.Positioning.Constraint.Alignment.InferAlign
        )
        try:
            network.AddConstraint(constraint)
        except Exception as error:
            if "duplicate" not in str(error).lower() and "already" not in str(error).lower():
                raise RuntimeError(
                    f"Flow 5 journal Touch kon niet aan het netwerk worden toegevoegd: {error}"
                )
        network.IsReferencedGeometryLoaded()
        network.Solve()
        blank_ref.SetFixHint(False)
        setup.end_network(positioner, network, session)
        network = None

        for line in helper_lines:
            session.UpdateManager.AddObjectsToDeleteList([line])
        session.UpdateManager.DoUpdate(session.NewestVisibleUndoMark)
        helper_lines = []
    finally:
        if network is not None:
            try:
                positioner.PrimaryArrangement = None
                positioner.ClearNetwork()
                positioner.EndAssemblyConstraints()
            except Exception:
                pass
        for line in helper_lines:
            try:
                session.UpdateManager.AddObjectsToDeleteList([line])
            except Exception:
                pass

    after = snapshot_constraint_states(machine_part)
    new_tags = set(after) - set(before)
    if len(new_tags) != 1:
        raise RuntimeError(
            "Flow 5 journal Touch maakte niet exact één nieuwe constraint: "
            f"voor={len(before)}, na={len(after)}, nieuw={new_tags}"
        )
    new_status = after[next(iter(new_tags))][0]
    if new_status not in {"0", "7", "9"}:
        raise RuntimeError(
            f"Flow 5 journal Touch heeft status {new_status}."
        )
    print(
        "Flow 5 journal-stap: Touch tussen MAIN chuck FACE 2142 en "
        f"{blank_stem} binnenboring {bore_faces[0].JournalIdentifier} toegevoegd; status={new_status}.",
        flush=True,
    )
    return constraint

"""Active builders extracted from Setup_Generator/nx_setup_step3.py."""

from pathlib import Path
import math
import re

def dispose(status):
    if isinstance(status, (tuple, list)):
        for item in status:
            dispose(item)
    elif status is not None and hasattr(status, "Dispose"):
        status.Dispose()



def open_base(session, path):
    path = Path(path).resolve()
    for loaded in session.Parts:
        if loaded.FullPath and Path(loaded.FullPath).resolve() == path:
            return loaded
    if not path.is_file():
        raise FileNotFoundError(path)
    result = session.Parts.OpenBase(str(path))
    if isinstance(result, tuple):
        part, status = result
        dispose(status)
        return part
    return result



def identity_matrix(NXOpen):
    matrix = NXOpen.Matrix3x3()
    matrix.Xx, matrix.Xy, matrix.Xz = 1.0, 0.0, 0.0
    matrix.Yx, matrix.Yy, matrix.Yz = 0.0, 1.0, 0.0
    matrix.Zx, matrix.Zy, matrix.Zz = 0.0, 0.0, 1.0
    return matrix



def determine_spanning_diameter(blank_part):
    """Bepaal de buitendiameter van de echte blank in de 50-mm-grijpzone.

    ``_BLANK.prt`` bevat naast de eigenlijke blank ook een linked source-body
    van het product. Die source-body mag niet worden gebruikt: daarin zit de
    eerdere Ø356 mm productgeometrie. De blank wordt daarom uitsluitend uit de
    expliciet benoemde ``BLANK_REVOLVE_OUTLINE_BODY`` gelezen. De UF-cylinder-
    data levert de modelmaten rechtstreeks in millimeters en is niet afhankelijk
    van de tekstuele JournalIdentifier.
    """
    import NXOpen.UF

    outline_body = next(
        (
            body for body in blank_part.Bodies
            if body.Name.upper() == "BLANK_REVOLVE_OUTLINE_BODY"
        ),
        None,
    )
    if outline_body is None:
        raise RuntimeError(
            "De echte blank-body BLANK_REVOLVE_OUTLINE_BODY ontbreekt in _BLANK.prt."
        )

    uf = NXOpen.UF.UFSession.GetUFSession()
    face_data = []
    for face in outline_body.GetFaces():
        face_type, point, direction, box, radius, _radial_data, _norm_dir = (
            uf.Modeling.AskFaceData(face.Tag)
        )
        face_data.append((face_type, point, direction, box, radius))
    if not face_data:
        raise RuntimeError("De blank-body bevat geen bruikbare geometrie.")

    # AskFaceData.box is [xmin, ymin, zmin, xmax, ymax, zmax].
    z_start = min(float(data[3][2]) for data in face_data)
    z_end = z_start + 50.0
    candidates = []
    for face_type, point, direction, box, radius in face_data:
        # UF face type 16 is cylinder. De as moet met de product-Z-as samenvallen.
        if face_type != 16 or abs(abs(float(direction[2])) - 1.0) > 1e-6:
            continue
        face_z_min = float(box[2])
        face_z_max = float(box[5])
        if face_z_max < z_start - 1e-6 or face_z_min > z_end + 1e-6:
            continue
        radius_mm = float(radius)
        if radius_mm > 0.1:
            candidates.append((2.0 * radius_mm, float(point[2])))
    if not candidates:
        raise RuntimeError(
            f"Geen buitendiameter gevonden in grijpzone Z={z_start:.3f}..{z_end:.3f} mm."
        )
    diameter, diameter_z = max(candidates)
    return diameter, z_start, z_end, diameter_z



def jaw_candidates(device_root):
    pattern = re.compile(r"_(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)MM_([A-Z]+)$", re.IGNORECASE)
    candidates = []
    for device_file in device_root.rglob("*.prt"):
        if device_file.stem.upper().endswith("_PART"):
            continue
        match = pattern.search(device_file.stem)
        if not match:
            continue
        lower, upper = float(match.group(1)), float(match.group(2))
        part_file = device_file.with_name(device_file.stem + "_PART.prt")
        if part_file.is_file():
            candidates.append((lower, upper, device_file, part_file))
    return candidates



def select_jaw(spanning_diameter, device_root):
    if not math.isfinite(spanning_diameter) or spanning_diameter <= 0:
        raise ValueError("The blank gripping diameter must be finite and positive")
    matches = [candidate for candidate in jaw_candidates(device_root)
               if candidate[0] <= spanning_diameter <= candidate[1]]
    if not matches:
        raise RuntimeError(f"Geen klauwbereik gevonden voor spandiameter {spanning_diameter:.3f} mm.")
    return sorted(matches, key=lambda item: (item[1] - item[0], item[0]))[0]


def prototype_path(component):
    prototype = component.Prototype
    path = getattr(prototype, "FullPath", "")
    if not path:
        path = prototype.OwningPart.FullPath
    if not path:
        raise RuntimeError(f"Component prototype is not loaded: {component.DisplayName}")
    return Path(path).resolve()


def find_product_component(parent, stem):
    """Cloning remaps filenames, not necessarily occurrence display names."""
    matches = [
        child for child in parent.GetChildren()
        if prototype_path(child).stem.casefold() == stem.casefold()
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one prototype {stem} under {parent.DisplayName}; found {len(matches)}")
    return matches[0]


def require_setup_owned(obj, machine_part):
    if obj.OwningPart.Tag != machine_part.Tag:
        raise RuntimeError(f"Refusing to modify a shared library object: {obj.JournalIdentifier}")


def open_display(session, path):
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    part = next(
        (loaded for loaded in session.Parts
         if loaded.FullPath and Path(loaded.FullPath).resolve() == path),
        None,
    )
    if part is not None:
        dispose(session.Parts.SetDisplay(part, False, False))
        session.Parts.SetWork(part)
    else:
        result = session.Parts.OpenBaseDisplay(str(path))
        if isinstance(result, tuple):
            part, status = result
            dispose(status)
        else:
            part = result
    dispose(session.Parts.EnsurePartsLoadedFully([part], True))
    return part


def save_setup(machine_part, path):
    import NXOpen

    path = Path(path).resolve()
    if Path(machine_part.FullPath).resolve() == path:
        dispose(machine_part.Save(
            NXOpen.BasePart.SaveComponents.FalseValue,
            NXOpen.BasePart.CloseAfterSave.FalseValue,
        ))
    else:
        if path.exists():
            path.unlink()
        dispose(machine_part.SaveAs(str(path)))


def close_setup(machine_part):
    import NXOpen

    machine_part.Close(
        NXOpen.BasePart.CloseWholeTree.TrueValue,
        NXOpen.BasePart.CloseModified.CloseModified,
        None,
    )


def save_reopen(machine_part, path):
    import NXOpen

    save_setup(machine_part, path)
    close_setup(machine_part)
    return open_display(NXOpen.Session.GetSession(), path)


def publish_setup(machine_part, paths, label):
    """Publish only the setup file; never save modified library components."""
    staged = paths.work_dir / f"{paths.name}_{label}_FINAL.prt"
    save_setup(machine_part, staged)
    close_setup(machine_part)
    staged.replace(paths.part("SETUP"))


def load_product_parts(session, paths):
    parts = [open_base(session, paths.part(kind)) for kind in ("PART", "ASSY", "CAD4CAM", "BLANK")]
    dispose(session.Parts.EnsurePartsLoadedFully(parts, True))
    return parts


def require_local_product(machine_part, paths):
    product = find_product_component(machine_part.ComponentAssembly.RootComponent, paths.part("ASSY").stem)
    if prototype_path(product) != paths.part("ASSY"):
        raise RuntimeError("SETUP must reference the item-local ASSY")
    for kind in ("PART", "CAD4CAM", "BLANK"):
        child = find_product_component(product, paths.part(kind).stem)
        if prototype_path(child) != paths.part(kind):
            raise RuntimeError(f"ASSY must reference the item-local {kind}")
    return product



def begin_network(machine_part, NXOpen):
    positioner = machine_part.ComponentAssembly.Positioner
    arrangement = machine_part.ComponentAssembly.Arrangements.FindObject("Arrangement 1")
    positioner.PrimaryArrangement = arrangement
    network = positioner.EstablishNetwork()
    positioner.BeginAssemblyConstraints()
    network.NetworkArrangementsMode = NXOpen.Positioning.ComponentNetwork.ArrangementsMode.Existing
    network.DisplayComponent = None
    network.MoveObjectsState = True
    return positioner, network



def end_network(positioner, network, session):
    network.Solve()
    positioner.PrimaryArrangement = None
    positioner.ClearNetwork()
    positioner.EndAssemblyConstraints()
    session.UpdateManager.DoUpdate(session.NewestVisibleUndoMark)



def apply_one_journal_constraint(machine_part, NXOpen, session, movable_component, creator):
    """Maak precies één journal-constraintcyclus aan.

    De opgenomen journal sluit het positioner/network na iedere constraint.
    Dat is belangrijk: NX mag de volgende constraint niet in hetzelfde
    tijdelijke oplossingsnetwerk blijven combineren met de vorige.
    """
    positioner, network = begin_network(machine_part, NXOpen)
    # De opgenomen journal roept AddMovableObject niet aan. NX bepaalt het
    # bewegende component uit de eerste constraint-reference. De nested
    # _PART-occurrence wordt daarom alleen als referentie gebruikt; de parent
    # device-assembly mag niet als vrij bewegend object worden geregistreerd,
    # anders worden de interne device-constraints met het nieuwe netwerk
    # vermengd.
    creator_result = creator(positioner)
    if len(creator_result) == 2:
        _constraint, fixed_ref = creator_result
        helper_lines = []
    else:
        _constraint, fixed_ref, helper_lines = creator_result
    # Dit volgt bewust de opgenomen journal: CreateConstraint(true) registreert
    # de constraint al in het actieve network. Extra calls zoals
    # SetMovingGroup, AddConstraint en ApplyToModel veranderen de solvergroep
    # en veroorzaken juist conflicten met de bestaande assembly-constraints.
    try:
        network.AddConstraint(_constraint)
    except Exception as error:
        # In sommige NX2512-builds registreert CreateConstraint(true) de
        # constraint al automatisch; dan meldt AddConstraint een duplicate.
        # Alleen echte toevoegfouten mogen de run stoppen.
        if "duplicate" not in str(error).lower() and "already" not in str(error).lower():
            raise RuntimeError(f"Constraint kon niet aan het actieve network worden gekoppeld: {error}")
    network.IsReferencedGeometryLoaded()
    network.Solve()
    for line in helper_lines:
        session.UpdateManager.AddObjectsToDeleteList([line])
    network.Solve()
    fixed_ref.SetFixHint(False)
    end_network(positioner, network, session)
    return _constraint



def find_face(component, names):
    for name in names:
        try:
            return component.FindObject(name)
        except Exception:
            pass
    # Na een save/reopen kan NX de prototype-prefix in de JournalIdentifier
    # opnieuw serialiseren. Toon en probeer daarom de actuele prototype-face
    # identifiers, zonder op een andere geometrie te gokken.
    wanted_ids = {
        int(match.group(1))
        for name in names
        for match in [re.search(r"FACE (\d+)", name)]
        if match
    }
    try:
        prototype = component.Prototype
        for name in names:
            try:
                prototype_face = prototype.FindObject(name)
                return component.FindOccurrence(prototype_face)
            except Exception:
                pass
        prototype_part = prototype.OwningPart
        faces = []
        for body in prototype_part.Bodies:
            faces.extend(body.GetFaces())
        candidates = [
            face for face in faces
            if any(f"FACE {face_id}" in face.JournalIdentifier for face_id in wanted_ids)
        ]
        for face in candidates:
            try:
                return component.FindOccurrence(face)
            except Exception:
                try:
                    return component.FindObject(face.JournalIdentifier)
                except Exception:
                    pass
    except Exception as error:
        print(f"Prototype-faces niet leesbaar: {error}", flush=True)
    raise RuntimeError(f"Geen face-reference gevonden op component {component.DisplayName}: {names}")



def find_component_occurrence(parent, display_name):
    """Resolve een occurrence via dezelfde FindObject-route als de journal."""
    names = [
        f"COMPONENT {display_name}",
    ]
    names.extend(f"COMPONENT {display_name} {index}" for index in range(1, 10))
    for name in names:
        try:
            return parent.FindObject(name)
        except Exception:
            pass
    raise RuntimeError(
        f"Occurrence {display_name} niet gevonden onder {parent.DisplayName}."
    )



def find_component_occurrences(parent, display_name):
    """Vind alle gelijknamige directe occurrences onder één assembly-occurrence.

    ``FindObject("COMPONENT <naam>")`` geeft bij gelijknamige basisbekken
    steeds de eerste occurrence terug. Voor drie GBK_400_out-bekken is dat
    onjuist: de referentie moet per fysieke positie worden gekoppeld.
    """
    wanted = display_name.upper()
    matches = [
        child for child in parent.GetChildren()
        if child.DisplayName.upper() == wanted
    ]
    if len(matches) >= 1:
        return matches
    # Fallback voor een NX-context waarin GetChildren() nog niet volledig is
    # opgebouwd; suffixen zijn alleen een zoekmechanisme, geen plaatsingsregel.
    matches = []
    for index in range(1, 10):
        try:
            matches.append(parent.FindObject(f"COMPONENT {display_name} {index}"))
        except Exception:
            pass
    if not matches:
        raise RuntimeError(
            f"Geen occurrences {display_name} gevonden onder {parent.DisplayName}."
        )
    return matches



def match_occurrences_by_position(reference_components, candidate_components):
    """Koppel gelijke componentnamen één-op-één op hun fysieke positie."""
    if len(reference_components) != len(candidate_components):
        raise RuntimeError(
            "Aantal referentie-occurrences en kandidaat-occurrences verschilt: "
            f"{len(reference_components)} tegenover {len(candidate_components)}."
        )

    remaining = list(candidate_components)
    matched = []
    for reference in reference_components:
        reference_point, _matrix = reference.GetPosition()
        selected = min(
            remaining,
            key=lambda candidate: (
                (float(candidate.GetPosition()[0].X) - float(reference_point.X)) ** 2
                + (float(candidate.GetPosition()[0].Y) - float(reference_point.Y)) ** 2
                + (float(candidate.GetPosition()[0].Z) - float(reference_point.Z)) ** 2
            ),
        )
        matched.append(selected)
        remaining.remove(selected)
    return matched



def face_help_point(face, NXOpen):
    """Lees een bruikbaar help point in de actuele assembly-occurrence."""
    import NXOpen.UF

    uf = NXOpen.UF.UFSession.GetUFSession()
    _face_type, point, _direction, _box, _radius, _radial, _norm_dir = (
        uf.Modeling.AskFaceData(face.Tag)
    )
    result = NXOpen.Point3d(float(point[0]), float(point[1]), float(point[2]))
    return result



def jaw_perpendicular_vectors(base_point, NXOpen):
    """Bepaal de twee journal-perpendicularen uit de actuele jaw-positie."""
    radius = math.hypot(float(base_point.X), float(base_point.Y))
    if radius < 1e-9:
        raise RuntimeError("Kan de radiale jaw-richting niet bepalen uit het basisbekpunt.")
    radial_x = float(base_point.X) / radius
    radial_y = float(base_point.Y) / radius
    jaw_vector = NXOpen.Vector3d(-radial_y, radial_x, 0.0)
    base_vector = NXOpen.Vector3d(-radial_x, -radial_y, 0.0)
    return jaw_vector, base_vector



def add_component(assembly, part, name, point, matrix):
    result = assembly.AddComponent(part, "Entire Part", name, point, matrix, -1)
    if isinstance(result, tuple):
        component, status = result
        dispose(status)
    else:
        component = result
    if component is None:
        raise RuntimeError(f"NX heeft component {name} niet toegevoegd.")
    return component



def add_journal_align_lock(
    positioner, NXOpen, moving_component, moving_face,
    stationary_component, stationary_face, jaw_vector, base_vector,
    work_part,
):
    """Voer de gatconstraint uit zoals de opgenomen NX-journal.

    De journal maakt hiervoor geen Concentric- of Touch-constraint, maar een
    AlignLock met de jaw-reference eerst en de GBK-reference als tweede.
    """
    helper_lines = [
        work_part.Lines.CreateFaceAxis(
            moving_face, NXOpen.SmartObject.UpdateOption.AfterModeling
        ),
        work_part.Lines.CreateFaceAxis(
            stationary_face, NXOpen.SmartObject.UpdateOption.AfterModeling
        ),
    ]
    for line in helper_lines:
        line.SetVisibility(NXOpen.SmartObject.VisibilityOption.Visible)
    constraint = positioner.CreateConstraint(True)
    constraint.ConstraintType = NXOpen.Positioning.Constraint.Type.AlignLock
    moving_ref = constraint.CreateConstraintReference(
        moving_component, moving_face, True, False, False
    )
    stationary_ref = constraint.CreateConstraintReference(
        stationary_component, stationary_face, True, False, False
    )
    moving_ref.HelpPoint = face_help_point(moving_face, NXOpen)
    stationary_ref.HelpPoint = face_help_point(stationary_face, NXOpen)
    stationary_ref.SetFixHint(True)
    moving_ref.SetPrototypePerpendicularVector(jaw_vector)
    stationary_ref.SetPrototypePerpendicularVector(base_vector)
    return constraint, stationary_ref, helper_lines



def add_journal_touch(
    positioner, NXOpen, moving_component, moving_face,
    stationary_component, stationary_face, work_part,
):
    """Voer de vlakconstraint uit zoals de Touch-dialog uit de journal."""
    constraint = positioner.CreateConstraint(True)
    constraint.ConstraintType = NXOpen.Positioning.Constraint.Type.Touch
    moving_ref = constraint.CreateConstraintReference(
        moving_component, moving_face, False, False, False
    )
    stationary_ref = constraint.CreateConstraintReference(
        stationary_component, stationary_face, False, False, False
    )
    moving_ref.HelpPoint = face_help_point(moving_face, NXOpen)
    stationary_ref.HelpPoint = face_help_point(stationary_face, NXOpen)
    stationary_ref.SetFixHint(True)
    constraint.ConstraintAlignment = (
        NXOpen.Positioning.Constraint.Alignment.ContraAlign
    )
    # De journal gebruikt bij deze Touch de al aanwezige face-axis helperlijn
    # uit de voorafgaande selectie; de Touch-vlakken zelf zijn niet altijd
    # cilindrisch en CreateFaceAxis daarop zou NX laten crashen.
    return constraint, stationary_ref, []



def find_left_chuck_and_jaws(machine_part):
    candidates = []
    root = machine_part.ComponentAssembly.RootComponent
    for outer in root.GetChildren():
        if "SMW_KNCS" not in outer.DisplayName.upper():
            continue
        try:
            point, _matrix = outer.GetPosition()
        except Exception:
            continue
        assy = next((child for child in outer.GetChildren() if "OUT_ASSY" in child.DisplayName.upper()), None)
        jaws = [child for child in assy.GetChildren() if "GBK_400_OUT" in child.DisplayName.upper()] if assy else []
        if len(jaws) == 3:
            candidates.append((point.Z, assy, jaws))
    if not candidates:
        raise RuntimeError("De drie bestaande GBK_400_out-basisbekken zijn niet gevonden.")
    # MAIN_CHUCK is in dit machine-template de lage-Z-occurrence. De hoge-Z-
    # occurrence is SUB_CHUCK. Workflow 1 moet de drie MAIN-basisbekken als
    # constraintbasis gebruiken.
    return min(candidates, key=lambda item: item[0])



def find_outer_chuck_for_assy(machine_part, target_assy):
    """Vind de SMW-occurrence die de gekozen chuck-assy bevat.

    De Auto Align-journal gebruikt deze outer SMW-component als de tweede
    componentcontext, terwijl het geselecteerde vlak zelf op GBK_400_out zit.
    """
    root = machine_part.ComponentAssembly.RootComponent
    target_tag = getattr(target_assy, "Tag", None)
    for outer in root.GetChildren():
        if "SMW_KNCS" not in outer.DisplayName.upper():
            continue
        assy = next(
            (
                child
                for child in outer.GetChildren()
                if "OUT_ASSY" in child.DisplayName.upper()
            ),
            None,
        )
        if assy is not None and getattr(assy, "Tag", None) == target_tag:
            return outer
    raise RuntimeError("De outer SMW-component van de gekozen MAIN-klauwplaat is niet gevonden.")



def snapshot_constraint_baseline(machine_part):
    """Lees uitsluitend de constraints die vóór deze workflow al bestonden."""
    root = machine_part.ComponentAssembly.RootComponent
    stack = [root]
    constraints = {}
    while stack:
        component = stack.pop()
        try:
            for constraint in component.GetConstraints():
                tag = getattr(constraint, "Tag", None)
                if tag is not None:
                    constraints[tag] = (constraint, component.DisplayName)
        except Exception:
            pass
        try:
            stack.extend(component.GetChildren())
        except Exception:
            pass
    return constraints



def validate_all_assembly_constraints(machine_part, baseline_constraints, generated_constraints):
    """Accepteer alleen een volledig persistente, conflictvrije assembly.

    Na een NX save/reopen worden sommige object-tags opnieuw uitgegeven. Een
    tag-voor-tagvergelijking is daarom geen geldige conflictcontrole. De
    controle gebeurt op de complete constraintset: alle templateconstraints
    moeten aanwezig blijven, alle negen nieuwe constraints moeten zijn
    opgeslagen. ``NewlyCreated`` (status 0) is in NX geen conflictstatus;
    echte solverconflicten en niet-opgeloste toestanden blokkeren wel.
    """
    current_constraints = snapshot_constraint_baseline(machine_part)
    conflicts = []

    status_counts = {}
    conflict_statuses = {3, 4, 5, 6, 8, 10, 13, 16, 17, 18}
    for constraint, component_name in current_constraints.values():
        try:
            status = constraint.GetConstraintStatus()
            status_key = str(status)
            status_counts[status_key] = status_counts.get(status_key, 0) + 1
            if status in conflict_statuses:
                conflicts.append(
                    f"constraint tag={getattr(constraint, 'Tag', '?')}, "
                    f"component={component_name}, status={status}"
                )
        except Exception as error:
            conflicts.append(
                f"constraint component={component_name}, status-read-error={error}"
            )

    expected_count = len(baseline_constraints) + len(generated_constraints)
    if len(current_constraints) < expected_count:
        conflicts.append(
            f"constraintset is niet compleet: minimaal={expected_count}, "
            f"actueel={len(current_constraints)}"
        )

    print(
        "Constraintcontrole: "
        f"template={len(baseline_constraints)}, nieuw={len(generated_constraints)}, "
        f"actueel={len(current_constraints)}, statusverdeling={status_counts}"
    )
    if conflicts:
        raise RuntimeError(
            "Conflictcontrole mislukt; output wordt niet geaccepteerd: "
            + "; ".join(conflicts)
        )

"""Active workholding builders extracted from Setup_Generator/flow6/flow6_attach_holders.py."""

import NXOpen
import NXOpen.Features
import NXOpen.UF

from . import common as setup


def _flow6_displayables(feature):
    """Return the displayable output objects belonging to one history feature."""
    objects = []
    seen = set()
    for getter_name in ("GetEntities", "GetBodies"):
        getter = getattr(feature, getter_name, None)
        if getter is None:
            continue
        try:
            candidates = list(getter())
        except Exception:
            candidates = []
        for candidate in candidates:
            try:
                tag = int(candidate.Tag)
            except Exception:
                tag = id(candidate)
            if tag not in seen:
                seen.add(tag)
                objects.append(candidate)
    return objects



def _flow6_find_feature(machine_part, journal_identifier, name):
    """Find a history feature by journal ID, then by its stable displayed name."""
    try:
        feature = machine_part.Features.FindObject(journal_identifier)
    except Exception:
        feature = None
    if feature is not None:
        return feature
    wanted = str(name).upper()
    for candidate in machine_part.Features:
        if str(getattr(candidate, "Name", "")).upper() == wanted:
            return candidate
    return None



def _flow6_blank_history_object(displayable):
    """Blank one NX displayable without deleting or rebuilding its feature."""
    blank = getattr(displayable, "Blank", None)
    if blank is not None:
        blank()
        return
    set_visibility = getattr(displayable, "SetVisibility", None)
    if set_visibility is not None:
        set_visibility(NXOpen.SmartObject.VisibilityOption.Hidden)
        return
    raise RuntimeError(
        f"Model-history-object {type(displayable).__name__} kan niet worden verborgen."
    )



def _flow6_unblank_history_object(displayable):
    """Show one NX displayable without changing its geometry or parents."""
    unblank = getattr(displayable, "Unblank", None)
    if unblank is not None:
        unblank()
        return
    set_visibility = getattr(displayable, "SetVisibility", None)
    if set_visibility is not None:
        set_visibility(NXOpen.SmartObject.VisibilityOption.Visible)
        return
    raise RuntimeError(
        f"Model-history-object {type(displayable).__name__} kan niet worden getoond."
    )



def apply_flow6_main_inside_and_blank_link(session, machine_part, input_file, hide_history=True):
    """Set MAIN_INSIDE Delta Z, link MAIN_BL01 to BLANK and hide history."""
    inside = machine_part.Features.FindObject("POINT(6)")
    if inside is None or str(inside.Name).upper() != "MAIN_INSIDE":
        raise RuntimeError(
            "Flow 6 verwacht Point (6) MAIN_INSIDE; het bestaande punt ontbreekt."
        )
    z_expression = next(
        (
            expression for expression in inside.GetExpressions()
            if str(expression.Name).lower().endswith("_zdelta")
        ),
        None,
    )
    if z_expression is None:
        raise RuntimeError(
            "MAIN_INSIDE mist de bestaande Delta Z-expressie; er wordt geen nieuw punt aangemaakt."
        )
    setup.require_setup_owned(z_expression, machine_part)
    z_expression.RightHandSide = "10.000000"
    session.UpdateManager.DoUpdate(session.NewestVisibleUndoMark)
    if abs(float(z_expression.Value) - 10.0) > 1.0e-8:
        raise RuntimeError(
            f"MAIN_INSIDE Delta Z kon niet op 10 mm worden gezet: {z_expression.Value}."
        )

    root = machine_part.ComponentAssembly.RootComponent
    product = setup.find_product_component(root, input_file.stem)
    blank_stem = input_file.stem.removesuffix("_ASSY") + "_BLANK"
    blank_component = setup.find_product_component(product, blank_stem)
    blank_component.UpdateStructure([blank_component], 2, True)
    blank_path = input_file.with_name(blank_stem + ".prt")
    blank_part = setup.open_base(session, blank_path)
    session.Parts.EnsurePartsLoadedFully([blank_part], True)
    blank_body = next(
        (
            body for body in blank_part.Bodies
            if str(body.Name).upper() == "BLANK_REVOLVE_OUTLINE_BODY"
        ),
        None,
    )
    if blank_body is None:
        raise RuntimeError("BLANK_REVOLVE_OUTLINE_BODY ontbreekt in de BLANK-bronpart.")

    linked_body = _flow6_find_feature(machine_part, "LINKED_BODY(12)", "MAIN_BL01")
    if linked_body is None or str(linked_body.Name).upper() != "MAIN_BL01":
        raise RuntimeError(
            "Flow 6 verwacht Linked Body (12) MAIN_BL01; het bestaande feature ontbreekt."
        )
    setup.require_setup_owned(linked_body, machine_part)
    uf = NXOpen.UF.UFSession.GetUFSession()
    xform_result = uf.So.CreateXformAssyCtxt(
        machine_part.Views.WorkView.Tag,
        blank_component.Tag,
        0,
    )
    assembly_xform = xform_result[-1] if isinstance(xform_result, tuple) else xform_result
    if not uf.So.IsAssyCtxtXform(assembly_xform):
        raise RuntimeError("BLANK gaf geen geldige assembly-contexttransform.")
    uf.Wave.SetLinkData(linked_body.Tag, blank_body.Tag, assembly_xform, False)
    session.UpdateManager.DoUpdate(session.NewestVisibleUndoMark)

    probe = machine_part.Features.CreateExtractFaceBuilder(linked_body)
    try:
        wave_info = str(probe.GetWaveLinkInformation()[0])
    finally:
        probe.Destroy()
    if "_BLANK" not in wave_info.upper():
        raise RuntimeError(
            "Linked Body (12) MAIN_BL01 verwijst niet naar de BLANK-occurrence: "
            f"{wave_info}"
        )
    result_bodies = list(linked_body.GetBodies())
    if len(result_bodies) != 1:
        raise RuntimeError(
            "Linked Body (12) MAIN_BL01 levert niet exact één resultaat-body op: "
            f"{len(result_bodies)}."
        )

    if not hide_history:
        return float(z_expression.Value)

    # Apply the requested Model History display state only after all links are
    # complete.  This blanks the existing displayable outputs; it does not
    # delete features, suppress parents, or alter assembly constraints.
    main_body_feature = _flow6_find_feature(machine_part, "LINKED_BODY(10)", "MAIN")
    if main_body_feature is None or str(main_body_feature.Name).upper() != "MAIN":
        raise RuntimeError("Linked Body (10) MAIN ontbreekt voor de eindweergave.")
    for feature in machine_part.Features:
        feature_jid = str(getattr(feature, "JournalIdentifier", ""))
        if (
            feature is main_body_feature
            or feature_jid == "LINKED_BODY(10)"
            or feature_jid.startswith("LINKED_BODY(10:")
            or (
                str(getattr(feature, "Name", "")).upper() == "MAIN"
                and str(getattr(feature, "FeatureType", "")).upper() == "LINKED_BODY"
            )
        ):
            continue
        for displayable in _flow6_displayables(feature):
            _flow6_blank_history_object(displayable)
    for displayable in _flow6_displayables(main_body_feature):
        _flow6_unblank_history_object(displayable)
    session.UpdateManager.DoUpdate(session.NewestVisibleUndoMark)

    print(
        "Flow 6 MAIN_INSIDE/MAIN_BL01 ingesteld: "
        f"Delta Z={float(z_expression.Value):.6f} mm; "
        "Linked Body (12) bron=BLANK; "
        "Model History zichtbaar: alleen Linked Body (10) MAIN.",
        flush=True,
    )
    return float(z_expression.Value)



def validate_flow6_main_inside_and_blank_link(session, machine_part, input_file, check_history=True):
    """Validate Point (6), BLANK WAVE source and the saved display state."""
    inside = machine_part.Features.FindObject("POINT(6)")
    if inside is None or str(inside.Name).upper() != "MAIN_INSIDE":
        raise RuntimeError("Flow 6 reopencontrole: MAIN_INSIDE ontbreekt.")
    z_expression = next(
        (
            expression for expression in inside.GetExpressions()
            if str(expression.Name).lower().endswith("_zdelta")
        ),
        None,
    )
    if z_expression is None or abs(float(z_expression.Value) - 10.0) > 1.0e-8:
        value = None if z_expression is None else z_expression.Value
        raise RuntimeError(
            f"Flow 6 reopencontrole: MAIN_INSIDE Delta Z={value}; verwacht 10 mm."
        )
    linked_body = _flow6_find_feature(machine_part, "LINKED_BODY(12)", "MAIN_BL01")
    if linked_body is None or str(linked_body.Name).upper() != "MAIN_BL01":
        raise RuntimeError("Flow 6 reopencontrole: MAIN_BL01 ontbreekt.")
    probe = machine_part.Features.CreateExtractFaceBuilder(linked_body)
    try:
        wave_info = str(probe.GetWaveLinkInformation()[0])
    finally:
        probe.Destroy()
    if "_BLANK" not in wave_info.upper():
        raise RuntimeError(
            "Flow 6 reopencontrole: MAIN_BL01 heeft geen BLANK-bron: "
            f"{wave_info}"
        )

    if not check_history:
        return

    main_feature = _flow6_find_feature(machine_part, "LINKED_BODY(10)", "MAIN")
    if main_feature is None or str(main_feature.Name).upper() != "MAIN":
        raise RuntimeError("Flow 6 reopencontrole: Linked Body (10) MAIN ontbreekt.")
    hidden_count = 0
    visible_non_main = []
    for feature in machine_part.Features:
        jid = str(getattr(feature, "JournalIdentifier", ""))
        if (
            feature is main_feature
            or jid == "LINKED_BODY(10)"
            or jid.startswith("LINKED_BODY(10:")
            or (
                str(getattr(feature, "Name", "")).upper() == "MAIN"
                and str(getattr(feature, "FeatureType", "")).upper() == "LINKED_BODY"
            )
        ):
            continue
        for displayable in _flow6_displayables(feature):
            try:
                blanked = bool(displayable.IsBlanked)
            except Exception:
                continue
            if blanked:
                hidden_count += 1
            else:
                visible_non_main.append(
                    f"{jid}:{type(displayable).__name__}"
                )
    main_bodies = _flow6_displayables(main_feature)
    if not main_bodies or any(bool(body.IsBlanked) for body in main_bodies):
        raise RuntimeError("Flow 6 reopencontrole: Linked Body (10) MAIN is verborgen.")
    if visible_non_main:
        raise RuntimeError(
            "Flow 6 reopencontrole: niet-toegestane Model History-objecten zichtbaar: "
            + ", ".join(visible_non_main[:10])
        )
    print(
        "Flow 6 reopencontrole MAIN_INSIDE/MAIN_BL01/model history OK: "
        f"Delta Z={float(z_expression.Value):.6f} mm; bron=BLANK; "
        f"verborgen history-objecten={hidden_count}; zichtbaar=Linked Body (10) MAIN.",
        flush=True,
    )

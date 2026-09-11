"""Active workholding builders extracted from Setup_Generator/flow6/flow6_attach_holders.py."""

import NXOpen

from . import common as setup


def restore_input_product_visibility(machine_part, input_file):
    """Keep the existing input assembly visible in the generated setup.

    Flow 4 may reopen the input occurrence after solving the jaw parameter.
    NX can retain the child PART occurrence as blanked even though the
    assembly occurrence itself is active.  Restore only that existing child;
    CAD4CAM/BLANK visibility and the input structure are left untouched.
    """
    root = machine_part.ComponentAssembly.RootComponent
    product = setup.find_product_component(root, input_file.stem)
    product.UpdateStructure([product], 2, True)
    # Flow 6 saves the input _ASSY occurrence hidden.  Unblank the parent
    # temporarily while rebuilding the setup; it is hidden again as the last
    # display operation before the final SaveAs.
    if product.IsBlanked:
        product.Unblank()
    part_name = input_file.stem.removesuffix("_ASSY") + "_PART"
    part_component = setup.find_product_component(product, part_name)
    if hasattr(part_component, "LoadThisPartFully"):
        part_component.LoadThisPartFully()
    part_component.Unblank()
    session = NXOpen.Session.GetSession()
    session.UpdateManager.DoUpdate(session.NewestVisibleUndoMark)
    if part_component.IsBlanked:
        raise RuntimeError(
            f"De bestaande input-PART blijft verborgen: {part_component.DisplayName}"
        )
    print(
        f"Flow 4 productzichtbaarheid hersteld: {part_component.DisplayName} zichtbaar.",
        flush=True,
    )



def hide_flow6_input_assembly(machine_part, input_file):
    """Hide only the existing input _ASSY occurrence in the Assembly Navigator."""
    root = machine_part.ComponentAssembly.RootComponent
    product = setup.find_product_component(root, input_file.stem)
    if product is None:
        raise RuntimeError("De ingeladen _ASSY-occurrence ontbreekt in Flow 6.")
    product.UpdateStructure([product], 2, True)
    product.Blank()
    session = NXOpen.Session.GetSession()
    session.UpdateManager.DoUpdate(session.NewestVisibleUndoMark)
    if not product.IsBlanked:
        raise RuntimeError(
            f"De ingeladen _ASSY-occurrence kon niet worden verborgen: {product.DisplayName}"
        )
    print(
        f"Flow 6 Assembly Navigator: _ASSY verborgen: {product.DisplayName}.",
        flush=True,
    )



def validate_flow6_input_assembly_hidden(machine_part, input_file):
    """Confirm the saved input _ASSY occurrence is hidden locally."""
    root = machine_part.ComponentAssembly.RootComponent
    product = setup.find_product_component(root, input_file.stem)
    if product is None or not product.IsBlanked:
        state = None if product is None else product.IsBlanked
        raise RuntimeError(
            f"Flow 6 reopencontrole: _ASSY is niet verborgen; state={state}."
        )
    print(
        f"Flow 6 reopencontrole Assembly Navigator OK: _ASSY verborgen: {product.DisplayName}.",
        flush=True,
    )



def apply_input_blank_transparency(machine_part, input_file):
    """Restore the input blank's transparent display as a local occurrence override.

    The prepared input blank uses NX translucency 75.  The output assembly had
    retained the geometry and reference set but not that occurrence display
    override, which made the blank appear opaque.  Apply only translucency to
    the existing BLANK occurrence; do not change its geometry, position,
    reference set, color, or the source input file.
    """
    root = machine_part.ComponentAssembly.RootComponent
    product = setup.find_product_component(root, input_file.stem)
    product.UpdateStructure([product], 2, True)
    blank_stem = input_file.stem.removesuffix("_ASSY") + "_BLANK"
    blank_component = setup.find_product_component(product, blank_stem)
    session = NXOpen.Session.GetSession()
    display_modification = session.DisplayManager.NewDisplayModification()
    try:
        display_modification.ApplyToAllFaces = True
        # Keep this as an occurrence-level display override.  Applying to the
        # owning part could modify the shared input _BLANK.prt.
        display_modification.ApplyToOwningParts = False
        display_modification.NewTranslucency = 75
        display_modification.Apply([blank_component])
        session.UpdateManager.DoUpdate(session.NewestVisibleUndoMark)
    finally:
        display_modification.Dispose()
    print(
        f"Flow 4 transparantie hersteld op bestaande BLANK-occurrence: "
        f"{blank_component.DisplayName} (75%).",
        flush=True,
    )



def apply_saved_view_visibility(machine_part, input_file):
    """Zet de componentvisibility van de door de gebruiker opgeslagen view.

    Dit is dezelfde toestand als de Assembly Navigator-checkboxes in de
    referentie-output: machine-opbouw en templatehulpen verborgen, chucken,
    blank, product-assy en jaws zichtbaar. De product-_PART wordt alleen onder
    de product-assy verborgen; de nested jaw-_PART's blijven zichtbaar.
    """
    hidden_names = {
        "MULTUS_U4000_1SW-2000",
        "TEMPLATE_PART",
        "TEMPLATE_PART_BL01",
        "OKUMA_MULTUS_U4000_ASSY",
        "OKUMA_MULTUS_U4000_BASE",
        "OKUMA_MULTUS_U4000_DOOR",
        "OKUMA_MULTUS_U4000_TC1",
        "OKUMA_MULTUS_U4000_Z1-AXIS",
        "OKUMA_MULTUS_U4000_B1-AXIS",
        "OKUMA_MULTUS_U4000_Y1-AXIS",
        "OKUMA_MULTUS_U4000_CAPTOSPINDLE",
        "OKUMA_MULTUS_U4000_W-AXIS",
        "OKUMA_MULTUS_U4000_MAINSPINDLE",
        "OKUMA_MULTUS_U4000_SUBSPINDLE",
        "OKUMA_MULTUS_U4000_TOUCHSETTER",
        "OKUMA_MULTUS_U4000_MAINBASE",
    }
    root = machine_part.ComponentAssembly.RootComponent
    input_component = setup.find_product_component(root, input_file.stem)
    if input_component is None:
        raise RuntimeError(
            f"Input-assy {input_file.stem} ontbreekt bij het instellen van de opgeslagen view."
        )
    input_part_components = {
        child.Tag
        for child in input_component.GetChildren()
        if setup.prototype_path(child).stem.upper().endswith("_PART")
    }

    changed = 0
    stack = list(root.GetChildren())
    while stack:
        component = stack.pop(0)
        display_name = component.DisplayName.upper()
        should_hide = display_name in hidden_names or component.Tag in input_part_components
        if should_hide:
            component.Blank()
        else:
            component.Unblank()
        changed += 1
        stack.extend(component.GetChildren())
    print(f"Opgeslagen view ingesteld: {changed} componenten verwerkt.", flush=True)



def apply_journal_final_view(machine_part, NXOpen):
    """Sla de exacte eindcamera uit C:\\Heerbaart\\journal.cs op."""
    rotation = NXOpen.Matrix3x3()
    rotation.Xx = 0.0032572708640175932
    rotation.Xy = -0.51913438956050939
    rotation.Xz = 0.85468641954938818
    rotation.Yx = 0.99387941332217455
    rotation.Yy = -0.092696880280449673
    rotation.Yz = -0.06009159808692658
    rotation.Zx = 0.11042237980086755
    rotation.Zy = 0.8496509718477967
    rotation.Zz = 0.51565504368444248
    translation = NXOpen.Point3d(
        -466.7306981541567,
        -110.75881355569433,
        -994.377166609911,
    )
    origin = NXOpen.Point3d(
        153.89096493780647,
        595.35306685058276,
        914.45212058862762,
    )
    work_view = machine_part.ModelingViews.WorkView
    work_view.SetRotationTranslationScale(rotation, translation, 0.2531040414601492)
    work_view.SetOrigin(origin)
    machine_part.Views.Refresh()
    print("Journal-eindview ingesteld.", flush=True)

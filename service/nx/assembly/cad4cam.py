"""Active builders extracted from heerbaart_poc/operations/prepare_cad4cam.py."""

from pathlib import Path

from .display import apply_display
from ..setup.common import find_product_component

def run(context):
    import NXOpen
    import NXOpen.Assemblies
    import NXOpen.Features

    session = NXOpen.Session.GetSession()
    operation_name = context.get("operationName", "prepare_cad4cam")
    project_file = Path(context["currentFile"])
    item_name = context["name"]
    output_dir = Path(context["outputDir"])
    step_dir = Path(context["stepDir"])
    parameters = context.get("operationParameters", {})

    color = parameters.get("color", 36)
    transparency = parameters.get("transparency", 0)
    component_name = f"{item_name}_CAD4CAM"
    cad4cam_file = output_dir / f"{component_name}.prt"
    model_file = step_dir / "model1.prt"

    step_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    if model_file.exists():
        model_file.unlink()

    project_part = session.Parts.Work

    file_new = session.Parts.FileNew()
    file_new.UseBlankTemplate = False
    file_new.ApplicationName = "ModelTemplate"
    file_new.Units = NXOpen.Part.Units.Millimeters
    file_new.TemplateType = NXOpen.FileNewTemplateType.Item
    file_new.TemplatePresentationName = "Model"
    file_new.AllowTemplatePostPartCreationAction(False)
    file_new.TemplateFileName = "model-plain-1-mm-template.prt"
    file_new.NewFileName = str(model_file)
    file_new.MakeDisplayedPart = False

    component_builder = project_part.AssemblyManager.CreateNewComponentBuilder()
    component_builder.NewComponentName = component_name
    component_builder.ReferenceSetName = "MODEL"
    component_builder.NewFile = file_new
    component = component_builder.Commit()
    component_builder.Destroy()

    part_load_status = session.Parts.SetWorkComponent(
        component,
        NXOpen.PartCollection.RefsetOption.Entire,
        NXOpen.PartCollection.WorkComponentOption.Visible,
    )
    part_load_status.Dispose()

    cad4cam_part = session.Parts.Work
    wave_link_builder = cad4cam_part.BaseFeatures.CreateWaveLinkBuilder(
        NXOpen.Features.Feature.Null
    )
    extract_face_builder = wave_link_builder.ExtractFaceBuilder
    composite_curve_builder = wave_link_builder.CompositeCurveBuilder
    wave_datum_builder = wave_link_builder.WaveDatumBuilder
    mirror_body_builder = wave_link_builder.MirrorBodyBuilder

    composite_curve_builder.CurveFitData.Tolerance = 0.01
    composite_curve_builder.CurveFitData.AngleTolerance = 0.5
    composite_curve_builder.Section.SetAllowRefCrvs(False)
    composite_curve_builder.Section.DistanceTolerance = 0.01
    composite_curve_builder.Section.ChainingTolerance = 0.0095
    composite_curve_builder.Section.AngleTolerance = 0.5

    wave_link_builder.Type = NXOpen.Features.WaveLinkBuilder.Types.BodyLink
    wave_link_builder.CopyGroups = True
    wave_link_builder.InheritMaterial = True
    wave_datum_builder.DisplayScale = 2.0
    mirror_body_builder.ParentPartType = (
        NXOpen.Features.MirrorBodyBuilder.ParentPart.OtherPart
    )
    mirror_body_builder.InheritMaterial = True

    extract_face_builder.FaceOption = (
        NXOpen.Features.ExtractFaceBuilder.FaceOptionType.FaceChain
    )
    extract_face_builder.AngleTolerance = 45.0
    extract_face_builder.ParentPart = (
        NXOpen.Features.ExtractFaceBuilder.ParentPartType.OtherPart
    )
    extract_face_builder.Associative = True
    extract_face_builder.MakePositionIndependent = False
    extract_face_builder.FixAtCurrentTimestamp = False
    extract_face_builder.HideOriginal = True
    extract_face_builder.InheritDisplayProperties = True
    extract_face_builder.CopyThreads = True
    extract_face_builder.FeatureOption = (
        NXOpen.Features.ExtractFaceBuilder.FeatureOptionType.OneFeatureForAllBodies
    )
    extract_face_builder.CopyGroups = True
    extract_face_builder.InheritMaterial = True

    part_component = find_product_component(
        project_part.ComponentAssembly.RootComponent, f"{item_name}_PART"
    )
    source_bodies = list(part_component.Prototype.Bodies)
    if not source_bodies:
        raise RuntimeError(f"No bodies found in source component: {item_name}_PART")

    body = part_component.FindOccurrence(source_bodies[0])
    if body is None:
        raise RuntimeError(
            f"Could not resolve source body occurrence in component: {item_name}_PART"
        )

    rule_options = cad4cam_part.ScRuleFactory.CreateRuleOptions()
    rule_options.SetSelectedFromInactive(False)
    body_rule = cad4cam_part.ScRuleFactory.CreateRuleBodyDumb(
        [body],
        True,
        rule_options,
    )
    rule_options.Dispose()

    extract_face_builder.ExtractBodyCollector.ReplaceRules([body_rule], False)
    wave_feature = wave_link_builder.Commit()
    wave_feature.SetName("CAD4CAM_LINKED_BODY")
    wave_link_builder.Destroy()

    linked_body = list(cad4cam_part.Bodies)[0]
    linked_body.SetName("CAD4CAM_BODY")
    cad4cam_reference_set = cad4cam_part.CreateReferenceSet()
    cad4cam_reference_set.SetName("CAD4CAM")
    cad4cam_reference_set.SetAddComponentsAutomatically(False, False)
    cad4cam_reference_set.AddObjectsToReferenceSet([linked_body])

    part_load_status = session.Parts.SetWorkComponent(
        NXOpen.Assemblies.Component.Null,
        NXOpen.PartCollection.RefsetOption.Entire,
        NXOpen.PartCollection.WorkComponentOption.Visible,
    )
    part_load_status.Dispose()

    project_part = session.Parts.Work
    make_unique_builder = project_part.AssemblyManager.CreateMakeUniquePartBuilder()
    make_unique_builder.SelectedComponents.Add(component)
    model_part = session.Parts.FindObject("model1")
    model_part.SetMakeUniqueName(str(cad4cam_file))
    make_unique_builder.Commit()
    make_unique_builder.Destroy()

    part_load_status = session.Parts.SetWorkComponent(
        component,
        NXOpen.PartCollection.RefsetOption.Entire,
        NXOpen.PartCollection.WorkComponentOption.Visible,
    )
    part_load_status.Dispose()

    cad4cam_part = session.Parts.Work
    linked_body = list(cad4cam_part.Bodies)[0]
    linked_body_faces = list(linked_body.GetFaces())
    apply_display(session, NXOpen, linked_body_faces, color, transparency)
    body_identifier = linked_body.JournalIdentifier
    save_status = cad4cam_part.Save(
        NXOpen.BasePart.SaveComponents.FalseValue,
        NXOpen.BasePart.CloseAfterSave.FalseValue,
    )
    save_status.Dispose()

    part_load_status = session.Parts.SetWorkComponent(
        NXOpen.Assemblies.Component.Null,
        NXOpen.PartCollection.RefsetOption.Entire,
        NXOpen.PartCollection.WorkComponentOption.Visible,
    )
    part_load_status.Dispose()

    error_list = project_part.ComponentAssembly.ReplaceReferenceSetInOwners(
        "CAD4CAM",
        [component],
    )
    error_list.Dispose()

    save_status = project_part.Save(
        NXOpen.BasePart.SaveComponents.FalseValue,
        NXOpen.BasePart.CloseAfterSave.FalseValue,
    )
    save_status.Dispose()

    return {
        "status": "completed",
        "operation": operation_name,
        "inputFile": str(project_file),
        "outputFile": str(project_file),
        "cad4camFile": str(cad4cam_file),
        "component": component.Name,
        "color": color,
        "transparency": transparency,
        "state": {"cad4camBodyJournalIdentifier": body_identifier},
    }

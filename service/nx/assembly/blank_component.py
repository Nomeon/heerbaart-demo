"""Active builders extracted from heerbaart_poc/operations/prepare_blank.py."""

from pathlib import Path

from .revolve_blank import create_revolve_outline_blank
from .display import apply_display
from ..setup.common import find_product_component

def run(context):
    import NXOpen
    import NXOpen.Assemblies
    import NXOpen.Features
    import NXOpen.GeometricUtilities

    session = NXOpen.Session.GetSession()
    operation_name = context.get("operationName", "prepare_blank")
    project_file = Path(context["currentFile"])
    item_name = context["name"]
    output_dir = Path(context["outputDir"])
    step_dir = Path(context["stepDir"])
    parameters = context.get("operationParameters", {})
    distance_tolerance = parameters.get("distanceTolerance", 0.01)
    color = parameters.get("color", 87)
    transparency = parameters.get("transparency", 75)
    component_name = f"{item_name}_BLANK"
    blank_file = output_dir / f"{component_name}.prt"
    model_name = "model3"
    model_file = step_dir / f"{model_name}.prt"

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

    blank_part = session.Parts.Work
    wave_link_builder = blank_part.BaseFeatures.CreateWaveLinkBuilder(
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
    extract_face_builder.HideOriginal = False
    extract_face_builder.InheritDisplayProperties = True
    extract_face_builder.CopyThreads = True
    extract_face_builder.FeatureOption = (
        NXOpen.Features.ExtractFaceBuilder.FeatureOptionType.OneFeatureForAllBodies
    )
    extract_face_builder.CopyGroups = True
    extract_face_builder.InheritMaterial = True

    cad4cam_component = find_product_component(
        project_part.ComponentAssembly.RootComponent, f"{item_name}_CAD4CAM"
    )
    cad4cam_body_id = context["state"]["cad4camBodyJournalIdentifier"]
    body = cad4cam_component.FindObject(f"PROTO#.Bodies|{cad4cam_body_id}")

    rule_options = blank_part.ScRuleFactory.CreateRuleOptions()
    rule_options.SetSelectedFromInactive(False)
    body_rule = blank_part.ScRuleFactory.CreateRuleBodyDumb(
        [body],
        True,
        rule_options,
    )
    rule_options.Dispose()

    extract_face_builder.ExtractBodyCollector.ReplaceRules([body_rule], False)
    wave_feature = wave_link_builder.Commit()
    wave_feature.SetName("BLANK_SOURCE_LINKED_BODY")
    wave_link_builder.Destroy()

    linked_body = list(blank_part.Bodies)[0]
    linked_body.SetName("BLANK_SOURCE_BODY")
    blank_bodies = create_revolve_outline_blank(
        NXOpen,
        blank_part,
        linked_body,
        distance_tolerance,
        5.0,
        (0.0, 0.0, 1.0),
    )
    session.DisplayManager.BlankObjects([linked_body])

    for blank_body in blank_bodies:
        blank_body.SetName("BLANK_REVOLVE_OUTLINE_BODY")

    blank_reference_set = blank_part.CreateReferenceSet()
    blank_reference_set.SetName("BLANK")
    blank_reference_set.SetAddComponentsAutomatically(False, False)
    blank_reference_set.AddObjectsToReferenceSet(blank_bodies)

    part_load_status = session.Parts.SetWorkComponent(
        NXOpen.Assemblies.Component.Null,
        NXOpen.PartCollection.RefsetOption.Entire,
        NXOpen.PartCollection.WorkComponentOption.Visible,
    )
    part_load_status.Dispose()

    project_part = session.Parts.Work
    make_unique_builder = project_part.AssemblyManager.CreateMakeUniquePartBuilder()
    make_unique_builder.SelectedComponents.Add(component)
    model_part = session.Parts.FindObject(model_name)
    model_part.SetMakeUniqueName(str(blank_file))
    make_unique_builder.Commit()
    make_unique_builder.Destroy()

    save_status = component.Prototype.Save(
        NXOpen.BasePart.SaveComponents.FalseValue,
        NXOpen.BasePart.CloseAfterSave.FalseValue,
    )
    save_status.Dispose()

    project_part = session.Parts.Work
    error_list = project_part.ComponentAssembly.ReplaceReferenceSetInOwners(
        "BLANK",
        [component],
    )
    error_list.Dispose()

    apply_display(session, NXOpen, [component], color, transparency)

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
        "blankFile": str(blank_file),
        "component": component.Name,
        "color": color,
        "transparency": transparency,
    }

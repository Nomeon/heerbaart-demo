"""Active builders extracted from heerbaart_poc/operations/create_parent_assembly.py."""

from pathlib import Path
import math

from .orientation import rotation_matrix
from ..setup.common import identity_matrix
from .display import apply_display

def assembly_placement(NXOpen, orientation):
    matrix = identity_matrix(NXOpen)
    origin = NXOpen.Point3d(0.0, 0.0, 0.0)

    status = orientation.get("status") if orientation else None
    if not status:
        return origin, matrix, False

    transform = orientation["proposedTransform"]
    if status["requiresRotation"]:
        values = rotation_matrix(
            transform["rotationAxis"],
            math.radians(transform["rotationAngleDegrees"]),
            (0.0, 0.0, 0.0),
        )
        matrix = NXOpen.Matrix3x3()
        matrix.Xx, matrix.Xy, matrix.Xz = values[0:3]
        matrix.Yx, matrix.Yy, matrix.Yz = values[4:7]
        matrix.Zx, matrix.Zy, matrix.Zz = values[8:11]

    if status["requiresTranslation"]:
        translation = transform["translationAfterRotation"]
        origin = NXOpen.Point3d(
            float(translation[0]),
            float(translation[1]),
            float(translation[2]),
        )

    return origin, matrix, bool(
        status["requiresRotation"] or status["requiresTranslation"]
    )



def run(context):
    import NXOpen
    import NXOpen.Assemblies

    session = NXOpen.Session.GetSession()
    operation_name = context.get("operationName", "create_parent_assembly")
    part_file = Path(context["currentFile"])
    item_name = context["name"]
    output_dir = Path(context["outputDir"])
    step_dir = Path(context["stepDir"])
    orientation = context["state"].get("orientation")

    step_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    component_part = session.Parts.FindObject(part_file.stem)

    file_new = session.Parts.FileNew()
    file_new.UseBlankTemplate = False
    file_new.ApplicationName = "AssemblyTemplate"
    file_new.Units = NXOpen.Part.Units.Millimeters
    file_new.TemplateType = NXOpen.FileNewTemplateType.Item
    file_new.TemplatePresentationName = "Assembly"
    file_new.AllowTemplatePostPartCreationAction(False)
    file_new.TemplateFileName = "assembly-mm-template.prt"
    file_new.NewFileName = str(step_dir / "assembly1.prt")
    file_new.MakeDisplayedPart = True
    file_new.DisplayPartOption = NXOpen.DisplayPartOption.AllowAdditional
    file_new.Commit()
    file_new.Destroy()

    assembly_part = session.Parts.Work
    component_origin, component_matrix, orientation_applied = assembly_placement(
        NXOpen,
        orientation,
    )

    component, component_status = assembly_part.ComponentAssembly.AddMasterPartComponent(
        component_part,
        "None",
        part_file.stem,
        component_origin,
        component_matrix,
        -1,
    )
    component_status.Dispose()
    apply_display(session, NXOpen, [component], 87, 0)

    output_file = output_dir / f"{item_name}_ASSY.prt"
    save_status = assembly_part.SaveAs(str(output_file))
    save_status.Dispose()

    return {
        "status": "completed",
        "operation": operation_name,
        "inputFile": str(part_file),
        "outputFile": str(output_file),
        "component": component.Name,
        "orientation": orientation,
        "orientationApplied": orientation_applied,
    }

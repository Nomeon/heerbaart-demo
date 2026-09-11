"""Active builders extracted from heerbaart_poc/tools/display.py."""



def apply_display(session, NXOpen, objects, color, transparency):
    mark_id = session.SetUndoMark(
        NXOpen.Session.MarkVisibility.Visible,
        "Edit Object Display",
    )

    display_modification = session.DisplayManager.NewDisplayModification()
    display_modification.ApplyToAllFaces = True
    display_modification.ApplyToOwningParts = False
    display_modification.NewColor = color
    display_modification.NewTranslucency = transparency
    display_modification.EndPointDisplayState = False
    display_modification.Apply(objects)

    session.UpdateManager.DoUpdate(mark_id)
    display_modification.Dispose()

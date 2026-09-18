Imports System
Imports System.IO
Imports System.Reflection
Imports System.Collections
Imports NXOpen

Module SetupSheetExport
    Dim backend As Assembly
    Dim root As String
    Dim app As String
    Dim flags As BindingFlags = BindingFlags.Public Or BindingFlags.NonPublic Or BindingFlags.Static Or BindingFlags.Instance
    Function T(name As String) As Type
        Return backend.GetType("Backend." & name, True)
    End Function
    Function Make(name As String) As Object
        Return Activator.CreateInstance(T(name))
    End Function
    Function Typ(obj As Object) As Type
        If TypeOf obj Is Type Then Return CType(obj, Type)
        Return obj.GetType()
    End Function
    Function Instance(obj As Object) As Object
        If TypeOf obj Is Type Then Return Nothing
        Return obj
    End Function
    Function Prop(obj As Object, name As String) As Object
        Return Typ(obj).GetProperty(name, flags).GetValue(Instance(obj), Nothing)
    End Function
    Sub Put(obj As Object, name As String, value As Object)
        Typ(obj).GetProperty(name, flags).SetValue(Instance(obj), value, Nothing)
    End Sub
    Function Invoke(obj As Object, name As String, ParamArray args() As Object) As Object
        Return Typ(obj).InvokeMember(name, flags Or BindingFlags.InvokeMethod, Nothing, Instance(obj), args)
    End Function
    Sub Log(text As String)
        File.AppendAllText(Path.Combine(root, "export.log"), DateTime.Now.ToString("s") & " " & text & Environment.NewLine)
        Console.WriteLine(text)
    End Sub
    Function Resolve(sender As Object, e As ResolveEventArgs) As Assembly
        Dim name As String = New AssemblyName(e.Name).Name
        For Each ext As String In New String() {".dll", ".exe"}
            Dim path As String = IO.Path.Combine(app, name & ext)
            If File.Exists(path) Then Return Assembly.LoadFile(path)
        Next
        Return Nothing
    End Function
    Sub OpenBase(session As Session, path As String)
        For Each loaded As BasePart In session.Parts
            If String.Equals(IO.Path.GetFileName(loaded.FullPath), IO.Path.GetFileName(path), StringComparison.OrdinalIgnoreCase) Then Return
        Next
        Log("Opening " & path)
        Dim status As PartLoadStatus = Nothing
        session.Parts.OpenBase(path, status)
        status.Dispose()
    End Sub
    Sub CaptureSetupOverview(part As Part)
        ' This Okuma setup uses X as the vertical machine axis, not Z.
        ' Replace the vendor's canned isometric cover with an upright front view.
        Dim angle As Double = 20.0 * Math.PI / 180.0
        Dim elevation As Double = 10.0 * Math.PI / 180.0
        Dim rotation As New Matrix3x3()
        rotation.Xx = 0
        rotation.Xy = -Math.Sin(angle)
        rotation.Xz = Math.Cos(angle)
        rotation.Yx = Math.Cos(elevation)
        rotation.Yy = -Math.Sin(elevation) * Math.Cos(angle)
        rotation.Yz = -Math.Sin(elevation) * Math.Sin(angle)
        rotation.Zx = Math.Sin(elevation)
        rotation.Zy = Math.Cos(elevation) * Math.Cos(angle)
        rotation.Zz = Math.Cos(elevation) * Math.Sin(angle)
        part.ModelingViews.WorkView.Orient(rotation)
        part.ModelingViews.WorkView.Fit()
        part.Views.Refresh()
        Dim info As Object = Prop(T("BE"), "CamSetupInfo")
        Invoke(Prop(info, "ImageSet"), "GetCustomImage")
        Invoke(info, "SyncInterface")
        Log("Upright Okuma setup overview captured")
    End Sub
    Sub Main()
        root = Environment.GetEnvironmentVariable("HEERBAART_MSI_WORK")
        ' NX auto-test mode can invoke Main again while closing temporary parts.
        ' Each worker request exports once and keeps the first result.
        If File.Exists(Path.Combine(root, "success.txt")) OrElse File.Exists(Path.Combine(root, "error.txt")) Then Return
        app = Environment.GetEnvironmentVariable("HEERBAART_MSI_APP")
        Try
            Run()
            File.WriteAllText(Path.Combine(root, "success.txt"), "OK")
        Catch ex As Exception
            Log(ex.ToString())
            File.WriteAllText(Path.Combine(root, "error.txt"), ex.ToString())
        End Try
    End Sub
    Sub Run()
        Log("Starting Machining Setup Instructions PDF export")
        AddHandler AppDomain.CurrentDomain.AssemblyResolve, AddressOf Resolve
        
        Dim session As Session = Session.GetSession()
        Dim resource As String = Path.Combine(Environment.GetEnvironmentVariable("HEERBAART_MSI_CUSTOM"), "MACH", "resource")
        Dim item As String = Environment.GetEnvironmentVariable("HEERBAART_MSI_ITEM")
        Dim name As String = Environment.GetEnvironmentVariable("HEERBAART_MSI_NAME")
        For Each kind As String In New String() {"PART", "CAD4CAM", "BLANK", "ASSY"}
            OpenBase(session, Path.Combine(item, name & "_" & kind & ".prt"))
        Next
        For Each rel As String In New String() {
            "template_part/metric/template_part_BL01.prt", "template_part/metric/template_part.prt",
            "library/machine/installed_machines/Okuma_MultusU4000/graphics/Okuma_Multus_U4000_Door.prt",
            "library/device/graphics/__Components/GBK_400_out.prt",
            "library/device/graphics/__Components/KNCS-N_400-128_chuck.prt",
            "library/device/graphics/__Components/KNCS-N_400-128_adapter.prt",
            "library/device/graphics/SMW_KNCS-N_400-128-A8_OUT/SMW_KNCS-N_400-128-A8_out_assy.prt",
            "library/device/graphics/SMW_KNCS-N_400-128-A8_OUT/SMW_KNCS-N_400-128-A8_OUT.prt"}
            OpenBase(session, Path.Combine(resource, rel))
        Next
        Dim load As PartLoadStatus = Nothing
        Dim setup As BasePart = session.Parts.OpenBaseDisplay(Path.Combine(item, name & "_SETUP.prt"), load)
        For i As Integer = 0 To load.NumberUnloadedParts - 1
            Log("LOAD: " & load.GetPartName(i) & ": " & load.GetStatusDescription(i))
        Next
        load.Dispose()
        session.Parts.SetWork(CType(setup, Part))
        session.ApplicationSwitchImmediate("UG_APP_MANUFACTURING")
        If Not session.IsCamSessionInitialized() Then session.CreateCamSession()
        Log("SETUP opened. Batch=" & session.IsBatch & ", app=" & session.ApplicationName & ", work=" & session.Parts.Work.FullPath)
        Log("Initializing Siemens Machining Setup Instructions")
        ' LoadFile retains the vendor resource paths; LoadFrom uses NX's shadow-copy folder.
        backend = Assembly.LoadFile(Path.Combine(app, "Backend.dll"))
        Dim launcher As Assembly = Assembly.LoadFile(Path.Combine(app, "MachiningSetupInstructions.dll"))
        ' The supplied Program constructor initializes the NX/UF sessions normally.
        ' Main also opens WPF; the automatic journal only needs the export backend.
        Dim program As Object = Activator.CreateInstance(launcher.GetType("Program"))
        Invoke(T("BE"), "InitializeBE")
        Dim be As Type = T("BE")
        Dim settings As Object = Invoke(T("SU+ObjectsSerialize"), "ByteArrayToObject", File.ReadAllBytes(Path.Combine(app, "Settings", "AppSettings.ml")))
        Put(Prop(be, "IFrontEnd"), "ApplicationSettings", settings)
        Put(settings, "m_OpenPDF", False)
        Put(settings, "m_CSEForceGeneration", False)
        Put(settings, "m_KeepMCSGeometry", False)
        Put(settings, "CreateCSETimeReport", False)
        Put(settings, "m_CreateImageWithIPW", False)
        Dim prog As Object = Prop(Prop(be, "IFrontEnd"), "ProgramSettings")
        Put(prog, "ProgramScopeIsAll", True)
        Put(prog, "ProgramScopeName", "")
        For Each method As String In New String() {"SyncSetupInfo", "SyncProgramCollection", "SyncOperationCollection", "SyncToolCollection", "SyncFixtureCollection"}
            Log(method)
            Invoke(be, method, True)
            If method = "SyncSetupInfo" Then CaptureSetupOverview(CType(setup, Part))
        Next
        Dim container As Object = Invoke(T("SU+ObjectsSerialize"), "ByteArrayToObject", File.ReadAllBytes(Path.Combine(app, "Localization", "AppMSI.ml")))
        Dim translated As Object = Nothing
        For Each language As Object In CType(Prop(Prop(container, "AllTranslations"), "FullList"), IEnumerable)
            Dim languageName As String = Convert.ToString(Prop(language, "Language"))
            Log("LANG " & languageName)
            If languageName = "EN" Or languageName = "English" Then translated = language
        Next
        If translated Is Nothing Then Throw New Exception("English translation not found")
        Dim translation As Object = Make("UITranslation")
        Put(translation, "UITranslatedItem", translated)
        Log("Writing PDF")
        Dim pdf As String = Environment.GetEnvironmentVariable("HEERBAART_MSI_PDF")
        Dim result As Object = Invoke(Make("CreatePDF"), "Create_doc", pdf, Prop(be, "IBackEnd"), "en-US", settings, translation)
        Log("PDF result=" & Convert.ToString(result) & " exists=" & File.Exists(pdf))
        If Not Convert.ToBoolean(result) OrElse Not File.Exists(pdf) Then Throw New Exception("PDF export did not complete")
        Invoke(be, "closeAllTempParts")
        Invoke(program, "Dispose")
        ' Never save article parts or persistent app settings during PDF export.
    End Sub
End Module



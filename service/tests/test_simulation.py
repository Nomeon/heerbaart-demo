from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from nx.simulation import simulate_article
from nc_release import released_nc


class ExternalSimulationTests(unittest.TestCase):
    def test_only_complete_clean_unchanged_nc_is_released(self):
        cases = [("end", 0, False, True), ("stop", 0, False, False),
                 (None, 0, False, False), ("end", 1, False, False), ("end", 0, True, False)]
        for event, collisions, changed, passed in cases:
            with self.subTest(event=event, collisions=collisions, changed=changed), tempfile.TemporaryDirectory() as temp:
                item = Path(temp) / "73023059"
                custom = Path(temp) / "custom"
                item.mkdir(); custom.mkdir()
                nc = item / "73023059-SETUP.min"
                nc.write_text("NC for this article")
                callbacks = {}
                def play():
                    if changed:
                        nc.write_text("Changed while simulation was running")
                    if event:
                        callbacks[event]()
                channels = SimpleNamespace(AssignFile=Mock())
                panel = SimpleNamespace(
                    SimulationOptionsBuilder=SimpleNamespace(Commit=Mock()), ApplySimulationOptions=Mock(),
                    SetSpeed=Mock(), AddSimEnd=lambda fn: callbacks.update(end=fn),
                    AddSimStart=lambda fn: callbacks.update(start=fn), AddSimStop=lambda fn: callbacks.update(stop=fn),
                    GetSingleStepMode=lambda: 0, MachineTime="00:00:01.000",
                    PlayForward=play, Stop=Mock(), Destroy=Mock(),
                    GetDetailCount=lambda kind: collisions if kind == "Collision" else 0,
                    GetDetail=lambda *a: (True, 1, "Collision at line 42", 42, "O1234", "1"),
                )
                session = SimpleNamespace(IsCamSessionInitialized=lambda: True, BeginTaskEnvironment=Mock(),
                    ApplicationName="APP_NONE", IsBatch=True, ApplicationSwitchImmediate=Mock(), SetUndoMark=Mock(),
                    DeleteUndoMarksSetInTaskEnvironment=Mock(), EndTaskEnvironment=Mock())
                part = SimpleNamespace(KinematicConfigurator=SimpleNamespace(
                    CreateNcChannelSelectionData=lambda: channels, CreateIsvControlPanelBuilder=lambda *a: panel))
                sim = SimpleNamespace(IsvControlPanelBuilder=SimpleNamespace(
                    VisualizationType=SimpleNamespace(MachineCodeSimulateCse="CSE"),
                    DetailType=SimpleNamespace(**{name:name for name in ["Controller", "Limit", "Collision", "Gouge", "Singularity"]})))
                cam = SimpleNamespace(SimulationOptionsBuilder=SimpleNamespace(
                    SimulationDisplayMode=SimpleNamespace(SuppressAll="SuppressAll")))
                with patch.dict("sys.modules", {"NXOpen":SimpleNamespace(SIM=sim, CAM=cam,
                    Session=SimpleNamespace(GetSession=lambda:session, MarkVisibility=SimpleNamespace(Visible=1))),
                    "NXOpen.CAM":cam, "NXOpen.SIM":sim}), \
                    patch("nx.setup.common.load_product_parts"), \
                    patch("nx.setup.common.open_display", return_value=part), patch("nx.setup.common.close_setup"):
                    request = dict(item_dir=str(item), name="73023059", custom_dir=str(custom), work_dir=str(Path(temp)/"work"))
                    if passed:
                        self.assertTrue(simulate_article(request)["simulation_passed"])
                    else:
                        with self.assertRaisesRegex(RuntimeError, "niet geslaagd"):
                            simulate_article(request)
                channels.AssignFile.assert_called_once_with("1", str(nc))
                self.assertEqual(released_nc(item, "73023059") is not None, passed)

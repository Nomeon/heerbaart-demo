import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from nx.post import post_article


class PostArticleTests(unittest.TestCase):
    def test_output_belongs_to_requested_article_and_old_file_is_not_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            custom = root / "custom"
            custom.mkdir()
            program = SimpleNamespace(Name="O1234")
            post = Mock()
            part = SimpleNamespace(CAMSetup=SimpleNamespace(DeleteMachineCode=Mock(),
                                    PostprocessWithPostModeSetting=post))
            session = SimpleNamespace(IsCamSessionInitialized=lambda: True)
            cam = SimpleNamespace(CAMObject=SimpleNamespace(Status=SimpleNamespace(Complete=0, Repost=1, Approved=4)),
                CAMSetup=SimpleNamespace(OutputUnits=SimpleNamespace(PostDefined=0),
                    PostprocessSettingsOutputWarning=SimpleNamespace(PostDefined=0),
                    PostprocessSettingsReviewTool=SimpleNamespace(PostDefined=0),
                    PostprocessSettingsPostMode=SimpleNamespace(Normal=0)))
            with patch.dict("sys.modules", {"NXOpen": SimpleNamespace(CAM=cam,
                            Session=SimpleNamespace(GetSession=lambda: session)), "NXOpen.CAM": cam}), \
                 patch("nx.setup.common.load_product_parts"), \
                 patch("nx.setup.common.open_display", return_value=part), \
                 patch("nx.setup.common.close_setup"), patch("nx.variant._save_part"), \
                 patch("nx.cam._article_program", return_value=program), \
                 patch("nx.cam._program_operations", return_value=[SimpleNamespace(Name="CUT", GetStatus=lambda: 1, AskPathExists=lambda: True)]):
                for name in ("73023059", "73023060"):
                    item = root / name
                    item.mkdir()
                    request = dict(name=name, item_dir=str(item), work_dir=str(root / f"work-{name}"), custom_dir=str(custom))
                    target = item / f"{name}-SETUP.min"
                    target.write_text("old output")
                    post.side_effect = None
                    with self.assertRaisesRegex(RuntimeError, "geen NC-programma"):
                        post_article(request)
                    self.assertEqual(target.read_text(), "old output")
                    post.side_effect = lambda objects, machine, path, *args: Path(path).write_text("fresh NC")
                    result = post_article(request)
                    self.assertEqual(result["nc_program"], str(target))
                    self.assertEqual(target.read_text(), "fresh NC")
                    self.assertEqual(post.call_args.args[:2], ([program], "Okuma_MultusU4000_1SW"))

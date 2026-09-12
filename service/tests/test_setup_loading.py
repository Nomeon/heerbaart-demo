import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from nx.setup import common


def component(name, path=None):
    prototype = SimpleNamespace(FullPath=str(path), OwningPart=None) if path else SimpleNamespace(OwningPart=None)
    return SimpleNamespace(DisplayName=name, Prototype=prototype)


class SetupLoadingTests(unittest.TestCase):
    def test_product_lookup_skips_unloaded_helpers_and_uses_prototype(self):
        product = component("BASELINE_ASSY", Path("73023060_ASSY.prt").resolve())
        children = [component("template_part"), product, component("unloaded_chuck")]
        root = SimpleNamespace(DisplayName="SETUP", GetChildren=lambda: children)
        self.assertIs(common.find_product_component(root, "73023060_ASSY"), product)

    def test_unloaded_product_is_reported_without_name_fallback(self):
        child = component("BASELINE_ASSY")
        root = SimpleNamespace(DisplayName="SETUP", GetChildren=lambda: [child])
        with self.assertRaisesRegex(RuntimeError, "found 0; unloaded components:.*BASELINE_ASSY"):
            common.find_product_component(root, "BASELINE_ASSY")
        with self.assertRaisesRegex(RuntimeError, "prototype is not loaded: BASELINE_ASSY"):
            common.prototype_path(child)

    def test_duplicate_prototype_matches_are_rejected(self):
        children = [component("A", "BASELINE_ASSY.prt"), component("B", "BASELINE_ASSY.prt")]
        root = SimpleNamespace(DisplayName="SETUP", GetChildren=lambda: children)
        with self.assertRaisesRegex(RuntimeError, "found 2"):
            common.find_product_component(root, "BASELINE_ASSY")

    def test_unresolved_load_status_preserves_details_and_is_disposed(self):
        disposed = []
        status = SimpleNamespace(
            NumberUnloadedParts=1,
            GetPartName=lambda index: "missing.prt",
            GetStatusDescription=lambda index: "Invalid path name",
            Dispose=lambda: disposed.append(True),
        )
        with self.assertRaisesRegex(RuntimeError, "setup: missing.prt: Invalid path name"):
            common.check_load_status(status, "setup")
        self.assertEqual(disposed, [True])

    def test_library_parts_are_loaded_before_each_setup_open(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "SETUP.prt"
            target.touch()
            custom = Path(directory) / "custom"
            events = []
            library = []
            def open_base(session, path):
                self.assertTrue(path.is_relative_to(custom))
                events.append("library")
                part = SimpleNamespace(FullPath=str(path))
                library.append(part)
                return part
            def status():
                return SimpleNamespace(NumberUnloadedParts=0, Dispose=lambda: None)
            def open_setup(path):
                self.assertEqual(events[-8:], ["library"] * 8)
                events.append("setup")
                return SimpleNamespace(FullPath=path), status()
            class Parts:
                def __iter__(self):
                    return iter(())
                OpenBaseDisplay = staticmethod(open_setup)
                def EnsurePartsLoadedFully(self, parts, include_children):
                    self.assertion = include_children and parts[1:] == library[-8:]
                    return status()
            session = SimpleNamespace(Parts=Parts())
            with patch.object(common, "open_base", side_effect=open_base):
                common.open_display(session, target, custom)
                common.open_display(session, target, custom)
            self.assertTrue(session.Parts.assertion)
            self.assertEqual(events.count("library"), 16)
            self.assertEqual(events.count("setup"), 2)


if __name__ == "__main__":
    unittest.main()

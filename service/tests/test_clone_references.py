import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from nx.variant import _check_clone_references, _require_clone_loaded


class CloneReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.custom = root / "custom"
        self.library = self.custom / "MACH" / "resource"
        self.library.mkdir(parents=True)
        self.original = root / "jaw.prt"
        self.candidate = self.library / "jaw.prt"
        self.original.write_bytes(b"native part A")
        self.candidate.write_bytes(b"native part A")

    def test_identical_library_copy_is_allowed(self):
        _check_clone_references({self.original}, {self.candidate}, {}, self.custom)

    def test_same_name_and_size_with_different_contents_is_rejected(self):
        self.candidate.write_bytes(b"native part B")
        with self.assertRaisesRegex(RuntimeError, "jaw.prt"):
            _check_clone_references({self.original}, {self.candidate}, {}, self.custom)

    def test_baseline_source_cannot_be_replaced_even_with_identical_bytes(self):
        with self.assertRaisesRegex(RuntimeError, "changed an existing part reference"):
            _check_clone_references({self.original}, {self.candidate}, {"part": self.original}, self.custom)

    def test_incomplete_load_reports_nx_filenames_and_statuses(self):
        status = SimpleNamespace(Failed=True, UserAbort=False, NParts=1,
                                 FileNames=["missing_part"], Statuses=[720090])
        with self.assertRaisesRegex(RuntimeError, "missing_part.*720090"):
            _require_clone_loaded(status)

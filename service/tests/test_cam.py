import unittest
from types import SimpleNamespace
from unittest.mock import patch

from nx.cam import _article_program, _check_toolpaths, _program_operations


class ProgramSelection(unittest.TestCase):
    def setUp(self):
        class Group:
            def __init__(self, name, *members):
                self.Name = name
                self.members = members

            def GetMembers(self):
                return self.members

        class Operation:
            pass

        self.Group = Group
        self.Operation = Operation
        self.view = object()
        cam = SimpleNamespace(NCGroup=Group, Operation=Operation,
                              CAMSetupView=SimpleNamespace(ProgramOrder=self.view))
        self.modules = patch.dict("sys.modules", {
            "NXOpen": SimpleNamespace(CAM=cam), "NXOpen.CAM": cam,
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)

    def part(self, root):
        def get_root(view):
            self.assertIs(view, self.view)
            return root
        return SimpleNamespace(CAMSetup=SimpleNamespace(GetRoot=get_root))

    def test_only_named_program_and_its_nested_operations_are_selected(self):
        cut = self.Operation()
        program = self.Group("O1234", self.Group("TURNING", cut))
        root = self.Group("PROGRAM", self.Group("ONLYNOTES", self.Operation()),
                          self.Group("CONTAINER", program), self.Group("O9999", self.Operation()))
        selected = _article_program(self.part(root))
        self.assertIs(selected, program)
        self.assertEqual(_program_operations(selected), [cut])

    def test_missing_program_does_not_fall_back_to_entire_setup(self):
        with self.assertRaisesRegex(RuntimeError, "O1234 ontbreekt"):
            _article_program(self.part(self.Group("PROGRAM", self.Group("O9999", self.Operation()))))


def operation(name, status, path=True):
    return SimpleNamespace(Name=name, GetStatus=lambda: status, AskPathExists=lambda: path)


class ToolpathChecks(unittest.TestCase):
    def test_stale_existing_path_is_not_success(self):
        with self.assertRaisesRegex(RuntimeError, "VD_VOORVLAK_1"):
            _check_toolpaths([operation("VD_VOORVLAK_1", 2)], {0, 1, 4})

    def test_missing_path_is_not_success_even_with_complete_status(self):
        with self.assertRaisesRegex(RuntimeError, "toolpath=False"):
            _check_toolpaths([operation("VB_M8", 0, False)], {0, 1, 4})

    def test_repost_is_allowed_without_claiming_nc_was_posted(self):
        _check_toolpaths([operation("turn", 1), operation("mill", 0)], {0, 1, 4})

    def test_empty_program_is_not_success(self):
        with self.assertRaisesRegex(RuntimeError, "geen CAM-bewerkingen"):
            _check_toolpaths([], {0, 1, 4})

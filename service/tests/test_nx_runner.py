"""Keep the CSE journal on NX's runtime without changing other stages."""

import os
from pathlib import Path
import unittest
from unittest.mock import patch

from nx_runner import _environment, PROJECT_DIR


class RuntimeEnvironmentTests(unittest.TestCase):
    def test_simulation_library_override_does_not_change_other_stage_libraries(self):
        custom = Path("article-custom").resolve()
        simulation = Path("working-cse-custom").resolve()
        with patch.dict(os.environ, {"NX_SIMULATION_CUSTOM_DIR": str(simulation)}):
            for stage in ("simulation", "clone", "refresh", "cam", "post"):
                env = _environment(Path("nx-install"), custom, Path("request.json"),
                                   Path("result.json"), stage=stage)
                library = (simulation if stage == "simulation" else custom) / "MACH/resource/library"
                self.assertEqual(Path(env["UGII_CAM_LIBRARY_INSTALLED_MACHINES_DIR"]),
                                 library / "machine/installed_machines")
                self.assertEqual(Path(env["UGII_CAM_LIBRARY_DEVICE_GRAPHICS_PATH"]),
                                 custom / "MACH/resource/library/device/graphics")
                self.assertEqual(Path(env["UGII_ENV_FILE"]), custom / "UGII/ugii_env.dat")
                if stage == "simulation":
                    self.assertEqual(Path(env["UGII_CAM_LIBRARY_TOOL_GRAPHICS_PATH"]), library / "tool/graphics")

    def test_simulation_uses_bundled_runtime_despite_service_override(self):
        install = Path("nx-install").resolve()
        with patch.dict(os.environ, {"NX_PYTHON_HOME": str(Path("pixi-python").resolve())}):
            env = _environment(install, Path("custom"), Path("request.json"),
                               Path("result.json"), stage="simulation")
        home = install / "NXBIN" / "python"
        self.assertEqual(env["UGII_PYTHON_HOME"], str(home))
        self.assertEqual(env["UGII_PYTHON_LIBRARY_DIR"], str(home))
        self.assertEqual(env["UGII_PYTHONPATH"].split(os.pathsep),
                         [str(home), str(home / "Python312.zip"), str(PROJECT_DIR)])
        self.assertEqual(env["NX_ENABLE_HEADLESS_GRAPHICS"], "1")

    def test_other_stages_keep_configured_runtime(self):
        home = Path("pixi-python").resolve()
        with patch.dict(os.environ, {"NX_PYTHON_HOME": str(home)}):
            for stage in ("clone", "refresh", "cam", "post", None):
                with self.subTest(stage=stage):
                    env = _environment(Path("nx-install"), Path("custom"),
                                       Path("request.json"), Path("result.json"), stage=stage)
                    self.assertEqual(env["UGII_PYTHON_LIBRARY_DIR"], str(home))
                    self.assertIn(str(home / "Lib" / "site-packages"), env["UGII_PYTHONPATH"])

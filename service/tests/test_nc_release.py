import json
from pathlib import Path
import tempfile
import unittest

from nc_release import invalidate_release, nc_hash, released_nc


class NcReleaseTests(unittest.TestCase):
    def test_only_completed_external_simulation_of_exact_nc_releases_download(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp)
            nc = item / "73023059-SETUP.min"
            nc.write_text("posted NC")
            self.assertIsNone(released_nc(item, "73023059"))
            record = dict(passed=True, mode="external_nc", completed=True, nc_sha256=nc_hash(nc))
            proof = item / "simulation.json"
            for overrides in [dict(passed=False), dict(completed=False), dict(mode="internal_toolpath")]:
                proof.write_text(json.dumps({**record, **overrides}))
                self.assertIsNone(released_nc(item, "73023059"))
            proof.write_text(json.dumps(record))
            self.assertEqual(released_nc(item, "73023059"), nc)
            nc.write_text("changed NC")
            self.assertIsNone(released_nc(item, "73023059"))
            invalidate_release(item)
            self.assertFalse(proof.exists())

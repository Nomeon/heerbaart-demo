"""Analysis is independent of NX; the baseline consumes the exact same rows."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

import drawing_analysis
import pipeline
from api.main import app
from pdf_table import FamilyTable


class DrawingAnalysisTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "elster-rev-d"
        self.pdf = Path(self.temp.name) / "input.pdf"
        self.pdf.write_bytes(b"%PDF-test-Elster")
        self.table = FamilyTable.model_validate({"articles": [
            {"article_number": str(73023059 + i), "asme_class": "300", "schedule": "80s",
             "expressions": dict.fromkeys(("DT", "FA", "DR", "FR", "FB", "DS", "DL"), i + 1)}
            for i in range(18)
        ]})
        for target in ("pipeline.family_directory", "api.main.family_directory"):
            patcher = patch(target, return_value=self.root)
            patcher.start()
            self.addCleanup(patcher.stop)
        extractor = patch.object(drawing_analysis, "extract_table", new_callable=AsyncMock, return_value=self.table)
        self.extract = extractor.start()
        self.addCleanup(extractor.stop)

    async def upload(self, content=None, filename="drawing.pdf"):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.post("/drawings/analyze", files={
                "drawing": (filename, self.pdf.read_bytes() if content is None else content, "application/pdf")})

    async def test_upload_returns_18_choices_without_creating_family_or_starting_nx(self):
        with patch.object(pipeline, "run_nx", new_callable=AsyncMock) as nx:
            response = await self.upload()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["articleNumbers"], [r.article_number for r in self.table.articles])
        self.assertFalse(self.root.exists())
        nx.assert_not_awaited()

    async def test_repeated_upload_and_baseline_use_same_extraction(self):
        await self.upload()
        await self.upload()
        with patch.object(pipeline, "run_nx", new_callable=AsyncMock, return_value={}) as nx:
            await pipeline.prepare_baseline(self.pdf, "73023060")
        self.extract.assert_awaited_once()
        family = json.loads((self.root / "family.json").read_text())
        self.assertEqual(family["articles"], self.table.model_dump()["articles"])
        self.assertEqual(family["setup_stage"], "references")
        self.assertEqual(nx.await_args_list[0].args[0], "part")
        self.assertEqual((self.root / "drawing.pdf").read_bytes(), self.pdf.read_bytes())

    async def test_existing_family_supplies_original_dimensions_without_extraction(self):
        self.root.mkdir()
        (self.root / "family.json").write_text(self.table.model_dump_json())
        (self.root / "drawing.pdf").write_bytes(self.pdf.read_bytes())
        response = await self.upload()
        self.assertEqual(response.status_code, 200)
        self.extract.assert_not_awaited()

    async def test_replacement_pdf_does_not_use_previous_cached_choices(self):
        await self.upload()
        changed = self.table.model_copy(deep=True)
        changed.articles[0].article_number = "99999999"
        self.extract.return_value = changed
        response = await self.upload(b"%PDF-replacement")
        self.assertEqual(response.json()["articleNumbers"][0], "99999999")
        self.assertEqual(self.extract.await_count, 2)

    async def test_failed_analysis_can_be_retried_without_partial_family(self):
        self.extract.side_effect = RuntimeError("unreadable")
        with self.assertLogs("api.main", level="ERROR"):
            response = await self.upload()
        self.assertEqual(response.status_code, 422)
        self.assertFalse(self.root.exists())
        self.extract.side_effect = None
        self.assertEqual((await self.upload()).status_code, 200)

    async def test_invalid_and_empty_files_never_reach_extractor(self):
        for content, name in [(b"", "empty.pdf"), (b"not a PDF", "drawing.pdf"), (b"%PDF-test", "drawing.txt")]:
            self.assertEqual((await self.upload(content, name)).status_code, 422)
        self.extract.assert_not_awaited()

    async def test_oversized_file_never_reaches_extractor(self):
        with patch("api.main.MAX_ANALYSIS_BYTES", 5):
            self.assertEqual((await self.upload()).status_code, 413)
        self.extract.assert_not_awaited()

"""PDF retry and delivery must preserve the verified NC and CSE time."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
import pipeline
from api.dependencies import Job, JobQueue
from api.main import get_article_setup_sheet
from api.schema import JobStart, JobStatus
from api.store import JobStatusStore
from api.worker import JobWorker
from nc_release import nc_hash
from setup_sheet_runner import publish_setup_sheet


class SetupSheetResultTests(unittest.TestCase):
    def test_completed_pdf_survives_nx_auto_check_failure(self):
        import pymupdf
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            work = root / "work"
            work.mkdir()
            output = root / "73023061_INSTELBLAD.pdf"
            with pymupdf.open() as document:
                document.new_page().insert_text((72, 72), "73023061 setup sheet")
                document.save(work / output.name)
            (work / "success.txt").write_text("OK")
            (work / "nx.log").write_text("ATHENA_FAIL: Test failed with 1 internal errors")
            with self.assertLogs("setup_sheet_runner", level="WARNING"):
                result = publish_setup_sheet(work, output, 1)
            self.assertEqual(result["setup_sheet"], str(output))
            with pymupdf.open(output) as document:
                self.assertEqual(document.page_count, 1)

    def test_failed_or_incomplete_export_is_not_published(self):
        for code, completed, error, pdf in [
            (1, False, False, b"partial PDF"),
            (1, True, True, b"partial PDF"),
            (2, True, False, b"partial PDF"),
            (1, True, False, b"broken PDF"),
        ]:
            with self.subTest(code=code, completed=completed, error=error), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                work = root / "work"
                work.mkdir()
                output = root / "73023061_INSTELBLAD.pdf"
                (work / output.name).write_bytes(pdf)
                (work / "nx.log").write_text("ATHENA_FAIL: Test failed with 1 internal errors")
                if completed:
                    (work / "success.txt").write_text("OK")
                if error:
                    (work / "error.txt").write_text("Export failed")
                with self.assertRaises(Exception):
                    publish_setup_sheet(work, output, code)
                self.assertFalse(output.exists())
                self.assertFalse((work / "result.json").exists())


class SetupSheetTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.article = self.root / "73023059"
        self.article.mkdir()
        self.nc = self.article / "73023059-SETUP.min"
        self.nc.write_text("verified NC")
        self.release = self.article / "simulation.json"
        self.release.write_text(json.dumps(dict(passed=True, completed=True, mode="external_nc",
            nc_sha256=nc_hash(self.nc), machine_time="01:04:45.590")))
        self.pdf = self.article / "73023059_INSTELBLAD.pdf"
        self.family = dict(baseline_ready=True, articles=[dict(article_number="73023059", expressions={})])

    async def test_retry_exports_only_pdf_and_keeps_release(self):
        original = self.release.read_bytes()
        self.pdf.write_bytes(b"old PDF")
        progress = AsyncMock()
        async def export(stage, request, work):
            self.assertEqual(stage, "setup_sheet")
            self.assertFalse(self.pdf.exists())
            self.assertEqual(self.release.read_bytes(), original)
            self.assertEqual(progress.await_args.kwargs["simulation_time_seconds"], 3885.59)
            self.pdf.write_bytes(b"%PDF-1.4 new")
            return {"setup_sheet": str(self.pdf)}
        with patch.object(pipeline, "family_directory", return_value=self.root), \
             patch.object(pipeline, "run_nx", side_effect=export) as nx:
            result = await pipeline.generate_article(self.family, "73023059", progress, resume_from="setup_sheet")
        self.assertEqual(nx.await_count, 1)
        self.assertEqual(result["simulation_time_seconds"], 3885.59)
        self.assertEqual(self.release.read_bytes(), original)

    async def test_export_failure_keeps_simulation_time(self):
        store = JobStatusStore()
        store.create("cpdf001")
        job = Job(JobStart(job_id="cpdf001", material="1.4404", amount=1,
            action="retry_article", article_number="73023059", resume_from="setup_sheet"))
        with patch.object(pipeline, "family_directory", return_value=self.root), \
             patch.object(pipeline, "_load_family", return_value=self.family), \
             patch.object(pipeline, "run_nx", side_effect=RuntimeError("PDF failed")):
            with self.assertLogs("api.worker", level="ERROR"):
                await JobWorker(JobQueue(), store, AsyncMock())._process(job)
        result = store.get_status_by_id(job.job_id)
        self.assertEqual(result.status, JobStatus.FAILED)
        self.assertEqual(result.stage, "setup_sheet")
        self.assertEqual(result.simulation_time_seconds, 3885.59)
        self.assertTrue(self.release.exists())

    async def test_download_requires_pdf_and_current_simulated_nc(self):
        with patch("api.main.family_directory", return_value=self.root):
            with self.assertRaises(HTTPException):
                await get_article_setup_sheet("73023059")
            self.pdf.write_bytes(b"%PDF-1.4 test")
            response = await get_article_setup_sheet("73023059")
            self.assertEqual(response.media_type, "application/pdf")
            self.assertEqual(response.path, self.pdf)
            self.nc.write_text("changed NC")
            with self.assertRaises(HTTPException):
                await get_article_setup_sheet("73023059")
            with patch.object(pipeline, "family_directory", return_value=self.root), \
                 patch.object(pipeline, "run_nx", new_callable=AsyncMock) as nx:
                with self.assertRaises(ValueError):
                    await pipeline.generate_article(self.family, "73023059", resume_from="setup_sheet")
                nx.assert_not_awaited()

"""Workflow checks only; mocked journals do not verify native NX/CAM behavior."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pipeline
from api.dependencies import Job, JobQueue
from api.schema import JobStart, JobStatus
from api.store import JobStatusStore
from api.worker import JobWorker


class QuotationFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        directory = patch.object(pipeline, "family_directory", return_value=self.root)
        directory.start()
        self.addCleanup(directory.stop)
        self.family = {"articles": [{"article_number": "73023059", "expressions": {"DT": 193.7}}],
                       "setup_stage": "references", "baseline_ready": False}
        (self.root / "BASELINE").mkdir()
        for kind in pipeline.PART_KINDS:
            (self.root / "BASELINE" / f"BASELINE_{kind}.prt").touch()
        pipeline._save_family(self.family)

    async def test_existing_baseline_waits_without_rebuilding(self):
        with patch.object(pipeline, "run_nx", new_callable=AsyncMock) as nx:
            result = await pipeline.run_job("prepare_quotation", article_number="73023059")
        self.assertEqual(result["outcome"], "AWAITING_PROGRAMMING")
        self.assertTrue(Path(result["setup"]).is_file())
        nx.assert_not_awaited()

    async def test_new_family_is_prepared_then_waits(self):
        (self.root / "family.json").unlink()
        async def build(*args):
            pipeline._save_family(self.family)
        with patch.object(pipeline, "prepare_baseline", side_effect=build) as prepare:
            result = await pipeline.run_job("prepare_quotation", drawing_path="drawing.pdf", article_number="73023059")
        prepare.assert_awaited_once()
        self.assertEqual(result["outcome"], "AWAITING_PROGRAMMING")

    async def test_approval_reloads_readiness_and_generates_original_article(self):
        progress = AsyncMock()
        setup = str(self.root / "73023059" / "73023059_SETUP.prt")
        with patch.object(pipeline, "run_nx", new_callable=AsyncMock, return_value={"setup": setup}) as nx:
            result = await pipeline.run_job("approve_baseline_and_generate", article_number="73023059",
                                            material="LF2", amount=5, progress=progress)
        self.assertTrue(json.loads((self.root / "family.json").read_text())["baseline_ready"])
        self.assertEqual([call.args[0] for call in nx.await_args_list], ["clone", "update", "refresh"])
        self.assertEqual(nx.await_args_list[0].args[1]["material"], "LF2")
        self.assertEqual(nx.await_args_list[0].args[1]["name"], "73023059")
        self.assertEqual([call.args[0] for call in progress.await_args_list], ["article_clone", "geometry_update", "setup_refresh"])
        self.assertEqual(result["outcome"], "ARTICLE_CREATED")

    async def test_ready_baseline_skips_preparation(self):
        pipeline._save_family({**self.family, "baseline_ready": True})
        with patch.object(pipeline, "run_nx", new_callable=AsyncMock, return_value={"setup": "article.prt"}) as nx:
            result = await pipeline.run_job("prepare_quotation", article_number="73023059")
        self.assertEqual(nx.await_count, 3)
        self.assertEqual(result["workflow"], "article")

    async def test_worker_keeps_failed_stage(self):
        store = JobStatusStore()
        store.create("ctest001")
        notifier = AsyncMock()
        worker = JobWorker(JobQueue(), store, notifier)
        job = Job(JobStart(job_id="ctest001", material="LF2", amount=1,
                           action="approve_baseline_and_generate", article_number="73023059"))
        with patch.object(pipeline, "run_nx", new_callable=AsyncMock, side_effect=RuntimeError("NX clone failed")):
            with self.assertLogs("api.worker", level="ERROR"):
                await worker._process(job)
        result = store.get_status_by_id("ctest001")
        self.assertEqual(result.status, JobStatus.FAILED)
        self.assertEqual(result.stage, "article_clone")
        self.assertEqual(result.error, "NX clone failed")

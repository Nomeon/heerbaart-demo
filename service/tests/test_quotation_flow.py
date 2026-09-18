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
from api.main import start_nx_job
from api.schema import JobStartForm


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
        with patch.object(pipeline, "run_nx", new_callable=AsyncMock, return_value={"simulation_time_seconds": 3885.59, "setup": setup, "weights": {"product_kg": 143.4, "stock_kg": 196.5}}) as nx:
            result = await pipeline.run_job("approve_baseline_and_generate", article_number="73023059",
                                            material="LF2", amount=5, progress=progress)
        self.assertTrue(json.loads((self.root / "family.json").read_text())["baseline_ready"])
        self.assertEqual([call.args[0] for call in nx.await_args_list], ["clone", "update", "measurement", "refresh", "cam", "post", "simulation", "setup_sheet"])
        self.assertEqual(nx.await_args_list[0].args[1]["material"], "LF2")
        self.assertEqual(nx.await_args_list[0].args[1]["name"], "73023059")
        self.assertEqual([call.args[0] for call in progress.await_args_list], ["article_clone", "geometry_update", "measurement", "measurement", "setup_refresh", "cam_regeneration", "postprocessing", "simulation", "setup_sheet"])
        self.assertEqual(result["outcome"], "ARTICLE_CREATED")

    async def test_ready_baseline_skips_preparation(self):
        pipeline._save_family({**self.family, "baseline_ready": True})
        with patch.object(pipeline, "run_nx", new_callable=AsyncMock, return_value={"simulation_time_seconds": 3885.59, "setup": "article.prt", "weights": {"product_kg": 143.4, "stock_kg": 196.5}}) as nx:
            result = await pipeline.run_job("prepare_quotation", article_number="73023059")
        self.assertEqual(nx.await_count, 8)
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

    def prepare_article_retry(self):
        pipeline._save_family({**self.family, "baseline_ready": True})
        article = self.root / "73023059"
        article.mkdir()
        for kind in pipeline.PART_KINDS:
            (article / f"73023059_{kind}.prt").write_text("operator-repaired article")
        return article

    async def test_refresh_retry_keeps_repaired_parts_and_skips_clone_update(self):
        article = self.prepare_article_retry()
        store = JobStatusStore()
        queue = JobQueue()
        form = JobStartForm(job_id="cretry001", material="LF2", amount=5,
                            article_number="73023059", action="retry_article", resume_from="setup_refresh")
        await start_nx_job(form, store, queue, AsyncMock())
        job = await queue.get()
        notifier = AsyncMock()
        with patch.object(pipeline, "run_nx", new_callable=AsyncMock,
                          return_value={"simulation_time_seconds": 3885.59, "setup": str(article / "73023059_SETUP.prt")}) as nx:
            await JobWorker(queue, store, notifier)._process(job)
        self.assertEqual([call.args[0] for call in nx.await_args_list], ["refresh", "cam", "post", "simulation", "setup_sheet"])
        self.assertEqual(nx.await_args.args[1]["amount"], 5)
        self.assertEqual(store.get_status_by_id("cretry001").outcome, "ARTICLE_CREATED")
        self.assertEqual(store.get_status_by_id("cretry001").stage, "setup_sheet")
        self.assertEqual((article / "73023059_SETUP.prt").read_text(), "operator-repaired article")

    async def test_geometry_retry_runs_update_then_refresh(self):
        self.prepare_article_retry()
        with patch.object(pipeline, "run_nx", new_callable=AsyncMock, return_value={"simulation_time_seconds": 3885.59, "weights": {"product_kg": 143.4, "stock_kg": 196.5}}) as nx:
            await pipeline.run_job("retry_article", article_number="73023059", resume_from="geometry_update")
        self.assertEqual([call.args[0] for call in nx.await_args_list], ["update", "measurement", "refresh", "cam", "post", "simulation", "setup_sheet"])

    async def test_cam_retry_runs_only_cam_through_api_and_reports_failure(self):
        self.prepare_article_retry()
        queue, store = JobQueue(), JobStatusStore()
        form = JobStartForm(job_id="ccamretry", material="LF2", amount=5,
                            article_number="73023059", action="retry_article", resume_from="cam_regeneration")
        await start_nx_job(form, store, queue, AsyncMock())
        notifier = AsyncMock()
        with patch.object(pipeline, "run_nx", new_callable=AsyncMock,
                          side_effect=RuntimeError("VD_VOORVLAK_1 requires regeneration")) as nx:
            with self.assertLogs("api.worker", level="ERROR"):
                await JobWorker(queue, store, notifier)._process(await queue.get())
        self.assertEqual([call.args[0] for call in nx.await_args_list], ["cam"])
        result = store.get_status_by_id("ccamretry")
        self.assertEqual(result.status, JobStatus.FAILED)
        self.assertEqual(result.stage, "cam_regeneration")
        self.assertIsNone(result.outcome)

    async def test_missing_retry_part_does_not_reclone(self):
        article = self.prepare_article_retry()
        (article / "73023059_SETUP.prt").unlink()
        with patch.object(pipeline, "run_nx", new_callable=AsyncMock) as nx:
            with self.assertRaises(FileNotFoundError):
                await pipeline.run_job("retry_article", article_number="73023059", resume_from="setup_refresh")
        nx.assert_not_awaited()

    async def test_post_retry_uses_article_and_does_not_regenerate_or_reclone(self):
        article = self.prepare_article_retry()
        queue, store = JobQueue(), JobStatusStore()
        form = JobStartForm(job_id="cpostretry", material="LF2", amount=5,
                            article_number="73023059", action="retry_article", resume_from="postprocessing")
        await start_nx_job(form, store, queue, AsyncMock())
        with patch.object(pipeline, "run_nx", new_callable=AsyncMock,
                          return_value={"simulation_time_seconds": 3885.59, "setup": str(article / "73023059_SETUP.prt")}) as nx:
            await JobWorker(queue, store, AsyncMock())._process(await queue.get())
        self.assertEqual([call.args[0] for call in nx.await_args_list], ["post", "simulation", "setup_sheet"])
        self.assertEqual(nx.await_args.args[1]["name"], "73023059")
        self.assertEqual(nx.await_args.args[1]["item_dir"], str(article))
        self.assertEqual(store.get_status_by_id("cpostretry").stage, "setup_sheet")
        self.assertEqual(store.get_status_by_id("cpostretry").status, JobStatus.COMPLETED)

    async def test_failed_retry_keeps_stage_for_another_attempt(self):
        self.prepare_article_retry()
        store = JobStatusStore()
        store.create("cretry002")
        job = Job(JobStart(job_id="cretry002", material="LF2", amount=1,
                           action="retry_article", article_number="73023059", resume_from="setup_refresh"))
        with patch.object(pipeline, "run_nx", new_callable=AsyncMock, side_effect=RuntimeError("Still missing constraints")):
            with self.assertLogs("api.worker", level="ERROR"):
                await JobWorker(JobQueue(), store, AsyncMock())._process(job)
        self.assertEqual(store.get_status_by_id("cretry002").status, JobStatus.FAILED)
        self.assertEqual(store.get_status_by_id("cretry002").stage, "setup_refresh")

    async def test_simulation_retry_never_reposts_and_stopped_simulation_fails(self):
        article = self.prepare_article_retry()
        (article / "simulation.json").write_text('{"passed": true}')
        queue, store = JobQueue(), JobStatusStore()
        await start_nx_job(JobStartForm(job_id="csimretry", material="LF2", amount=1,
            article_number="73023059", action="retry_article", resume_from="simulation"), store, queue, AsyncMock())
        with patch.object(pipeline, "run_nx", new_callable=AsyncMock,
                          side_effect=RuntimeError("External simulation stopped at collision")) as nx:
            with self.assertLogs("api.worker", level="ERROR"):
                await JobWorker(queue, store, AsyncMock())._process(await queue.get())
        self.assertEqual([call.args[0] for call in nx.await_args_list], ["simulation"])
        self.assertEqual(store.get_status_by_id("csimretry").status, JobStatus.FAILED)
        self.assertEqual(store.get_status_by_id("csimretry").stage, "simulation")
        self.assertFalse((article / "simulation.json").exists())

    async def test_measurement_sends_per_piece_weights_before_cam(self):
        article = self.prepare_article_retry()
        release = article / "simulation.json"
        release.write_text('{"passed": true}')
        store, notifier = JobStatusStore(), AsyncMock()
        store.create("cweights001")
        weights = {"product_kg": 143.396632404, "stock_kg": 196.507583286}
        job = Job(JobStart(job_id="cweights001", material="1.4301 - RVS 304", amount=5,
                           action="retry_article", article_number="73023059", resume_from="measurement"))
        async def journal(stage, *_):
            if stage == "cam":
                sent = notifier.send_status.await_args_list
                early = next(call.kwargs for call in sent if call.kwargs.get("weights"))
                self.assertEqual(early["status"], JobStatus.IN_PROGRESS)
                self.assertEqual(early["stage"], "measurement")
                self.assertEqual(early["weights"], weights)
                self.assertIsNone(early["simulation_time_seconds"])
            if stage == "simulation":
                return {"simulation_time_seconds": 3888.790}
            return {"weights": weights} if stage == "measurement" else {}
        with patch.object(pipeline, "run_nx", new_callable=AsyncMock, side_effect=journal) as nx:
            await JobWorker(JobQueue(), store, notifier)._process(job)
        self.assertEqual([call.args[0] for call in nx.await_args_list], ["measurement", "refresh", "cam", "post", "simulation", "setup_sheet"])
        self.assertFalse(release.exists())
        result = store.get_status_by_id(job.job_id)
        self.assertEqual(result.status, JobStatus.COMPLETED)
        self.assertEqual(result.stage, "setup_sheet")
        self.assertEqual(result.weights.model_dump(), weights)
        self.assertEqual(notifier.send_status.await_args.kwargs["weights"], weights)
        self.assertEqual(notifier.send_status.await_args.kwargs["simulation_time_seconds"], 3888.790)

    async def test_measurement_failure_does_not_report_completed_weights(self):
        self.prepare_article_retry()
        store, notifier = JobStatusStore(), AsyncMock()
        store.create("cweights002")
        job = Job(JobStart(job_id="cweights002", material="1.4301 - RVS 304", amount=5,
                           action="retry_article", article_number="73023059", resume_from="measurement"))
        with patch.object(pipeline, "run_nx", new_callable=AsyncMock, side_effect=RuntimeError("NX measurement failed")):
            with self.assertLogs("api.worker", level="ERROR"):
                await JobWorker(JobQueue(), store, notifier)._process(job)
        result = store.get_status_by_id(job.job_id)
        self.assertEqual(result.status, JobStatus.FAILED)
        self.assertEqual(result.stage, "measurement")
        self.assertIsNone(result.weights)

    async def test_cam_failure_keeps_weights_already_sent_to_app(self):
        self.prepare_article_retry()
        store, notifier = JobStatusStore(), AsyncMock()
        store.create("cweights003")
        weights = {"product_kg": 143.4, "stock_kg": 196.5}
        job = Job(JobStart(job_id="cweights003", material="1.4301 - RVS 304", amount=5,
                           action="retry_article", article_number="73023059", resume_from="measurement"))
        async def journal(stage, *_):
            if stage == "cam":
                raise RuntimeError("CAM failed after weight delivery")
            return {"weights": weights} if stage == "measurement" else {}
        with patch.object(pipeline, "run_nx", side_effect=journal):
            with self.assertLogs("api.worker", level="ERROR"):
                await JobWorker(JobQueue(), store, notifier)._process(job)
        result = store.get_status_by_id(job.job_id)
        self.assertEqual(result.status, JobStatus.FAILED)
        self.assertEqual(result.stage, "cam_regeneration")
        self.assertEqual(result.weights.model_dump(), weights)

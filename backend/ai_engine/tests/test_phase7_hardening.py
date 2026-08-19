"""Phase 7 tests: scorecards, experimental stubs, checklist dry-run invariants."""

from __future__ import annotations

import unittest

from backend.ai_engine.models.catalog import bootstrap_models
from backend.ai_engine.models.manager import manager
from backend.ai_engine.ops.scorecard import (
    WORKFLOW_SCORES,
    disk_footprint_report,
    workflow_scorecard,
)
from backend.ai_engine.registry.catalog import bootstrap_workflows
from backend.ai_engine.registry.workflows import registry
from backend.ai_engine.runtime.engine import engine_health


class Phase7ScorecardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bootstrap_models()
        bootstrap_workflows(force=True)

    def test_stable_p1_p2_have_scores(self) -> None:
        required = [
            "clothing_replace.v1",
            "instruction_edit.v1",
            "background_remove.v1",
            "video_i2v.v1",
            "image_img2img.v0_legacy",
        ]
        for ref in required:
            wf = registry.get(ref)
            self.assertIsNotNone(wf, msg=ref)
            self.assertGreater(wf.benchmark_score, 0, msg=ref)
            self.assertTrue(wf.benchmark_estimated, msg=ref)
            self.assertEqual(wf.benchmark_score, WORKFLOW_SCORES[ref])

    def test_model_scores_stamped(self) -> None:
        flux = manager.get("backbone.flux_dev_fp8")
        assert flux is not None
        self.assertGreater(flux.benchmark_score, 0)
        self.assertGreater(flux.disk_mb, 0)
        self.assertTrue(flux.benchmark_estimated)

    def test_disk_footprint_documented(self) -> None:
        report = disk_footprint_report()
        self.assertGreater(report["total_catalog_disk_mb_est"], 0)
        self.assertEqual(report["recommended_free_gb"], 100)
        self.assertTrue(report["models"])


class Phase7ExperimentalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bootstrap_models()
        bootstrap_workflows(force=True)

    def test_stubs_registered(self) -> None:
        v2v = registry.get("video_v2v.experimental")
        ext = registry.get("video_extend.experimental")
        self.assertIsNotNone(v2v)
        self.assertIsNotNone(ext)
        assert v2v is not None and ext is not None
        self.assertTrue(v2v.experimental)
        self.assertTrue(ext.experimental)
        self.assertEqual(v2v.fallback_workflow_ref, "video_i2v.v1")
        self.assertEqual(ext.task_types, ["video.extend"])

    def test_stable_resolve_ignores_experimental(self) -> None:
        available = registry.available_task_types(channel="stable")
        self.assertNotIn("video.v2v", available)
        self.assertNotIn("video.extend", available)
        # Stable I2V still v1
        wf = registry.resolve("video.i2v", channel="stable")
        self.assertEqual(wf.workflow_ref, "video_i2v.v1")

    def test_experimental_channel_sees_stubs(self) -> None:
        available = registry.available_task_types(
            channel="experimental", allow_experimental=True
        )
        self.assertIn("video.v2v", available)
        self.assertIn("video.extend", available)
        wf = registry.resolve(
            "video.v2v", channel="experimental", allow_experimental=True
        )
        self.assertEqual(wf.workflow_ref, "video_v2v.experimental")

    def test_kill_switch(self) -> None:
        wf = registry.get("video_v2v.experimental")
        assert wf is not None
        prev = wf.enabled
        try:
            wf.enabled = False
            with self.assertRaises(KeyError):
                registry.resolve(
                    "video.v2v", channel="experimental", allow_experimental=True
                )
        finally:
            wf.enabled = prev


class Phase7HealthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bootstrap_models()
        bootstrap_workflows(force=True)

    def test_engine_health_summary_footer(self) -> None:
        h = engine_health(channel="stable")
        self.assertIn("summary", h)
        self.assertIn("footer", h["summary"])
        self.assertIn("runnable", h["summary"]["footer"])
        self.assertIn("disk", h)
        self.assertIn("scorecard", h)
        self.assertTrue(workflow_scorecard(channel="stable"))


if __name__ == "__main__":
    unittest.main()

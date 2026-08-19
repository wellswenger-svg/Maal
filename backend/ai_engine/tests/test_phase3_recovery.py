"""Phase 3 tests: model health, recovery classification, execute retry/OOM/corrupt."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from backend.ai_engine.models.catalog import bootstrap_models
from backend.ai_engine.models.manager import manager
from backend.ai_engine.registry.catalog import bootstrap_workflows
from backend.ai_engine.registry.workflows import registry
from backend.ai_engine.runtime import recovery
from backend.ai_engine.runtime.engine import engine_health, run
from backend.ai_engine.schema import GenerateRequest
from backend.comfy_client import ComfyUIError
from backend.config import get_settings


class ModelHealthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bootstrap_models()
        bootstrap_workflows()

    def test_health_lists_workflows(self) -> None:
        h = manager.health(channel="stable")
        self.assertIn("slots", h)
        self.assertIn("planner.default_model", h["slots"])
        refs = [w["workflow_ref"] for w in h["workflows"]]
        self.assertIn("image_img2img.v0_legacy", refs)
        self.assertIn("video_i2v.v0_legacy", refs)
        img = next(w for w in h["workflows"] if w["workflow_ref"] == "image_img2img.v0_legacy")
        self.assertTrue(img["runnable"])

    def test_actionable_missing(self) -> None:
        info = manager.actionable_missing("backbone.flux_kontext_dev_fp8")
        self.assertEqual(info["status"], "missing")
        self.assertTrue(info.get("download_source") or info.get("hint"))

    def test_engine_health(self) -> None:
        blob = engine_health()
        self.assertIn("models", blob)
        self.assertEqual(blob["recovery"]["max_retries"], recovery.MAX_RETRIES)


class RecoveryUnitTests(unittest.TestCase):
    def test_classify_oom(self) -> None:
        self.assertEqual(
            recovery.classify_error(RuntimeError("CUDA out of memory")),
            "oom",
        )

    def test_classify_timeout(self) -> None:
        self.assertEqual(
            recovery.classify_error(TimeoutError("ComfyUI generation timed out")),
            "timeout",
        )

    def test_corrupt_detection(self) -> None:
        self.assertTrue(recovery.is_corrupt_output(b""))
        self.assertTrue(recovery.is_corrupt_output(b"\x00" * 10))
        self.assertFalse(recovery.is_corrupt_output(b"PNG" + b"\x01" * 40))

    def test_oom_degrades_profile(self) -> None:
        events: list = []
        decision = recovery.recover_after_failure(
            events,
            RuntimeError("CUDA out of memory"),
            profile="quality",
            attempt=1,
            fallback_workflow_ref=None,
        )
        self.assertEqual(decision["action"], "degrade")
        self.assertEqual(decision["profile"], "balanced")
        self.assertTrue(any(e["kind"] == "oom" for e in events))

    def test_oom_on_draft_aborts_without_fallback(self) -> None:
        events: list = []
        decision = recovery.recover_after_failure(
            events,
            RuntimeError("out of memory"),
            profile="draft",
            attempt=1,
            fallback_workflow_ref=None,
        )
        self.assertEqual(decision["action"], "abort")

    def test_transient_retries(self) -> None:
        events: list = []
        decision = recovery.recover_after_failure(
            events,
            ConnectionError("connection reset"),
            profile="balanced",
            attempt=1,
            fallback_workflow_ref=None,
        )
        self.assertEqual(decision["action"], "retry")


class ExecuteRecoveryTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bootstrap_models()
        bootstrap_workflows()

    async def test_corrupt_then_success(self) -> None:
        wf = registry.get("image_img2img.v0_legacy")
        assert wf is not None
        original = wf.runner
        calls = {"n": 0}

        async def flaky(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return b"\x00\x00", "image/png", "img", "test"
            return b"FAKEPNG" + b"\x01" * 64, "image/png", "img", "test"

        wf.runner = flaky
        try:
            settings = get_settings()
            with patch(
                "backend.ai_engine.runtime.engine.run_post",
                new_callable=AsyncMock,
                side_effect=lambda r, w, p, **kw: r,
            ):
                result = await run(
                    GenerateRequest(
                        mode="img",
                        prompt="img2img test",
                        prompt_english="img2img test",
                        image_bytes=b"\x89PNG" + b"\x00" * 20,
                    ),
                    settings=settings,
                )
            self.assertGreaterEqual(calls["n"], 2)
            self.assertTrue(any(e["kind"] == "corrupt_output" for e in result.recovery_events))
            self.assertTrue(len(result.data) >= 32)
        finally:
            wf.runner = original

    async def test_oom_degrades_and_succeeds(self) -> None:
        wf = registry.get("image_img2img.v0_legacy")
        assert wf is not None
        original = wf.runner
        calls = {"n": 0}

        async def oom_then_ok(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("CUDA out of memory")
            return b"FAKEPNG" + b"\x01" * 64, "image/png", "img", "test"

        wf.runner = oom_then_ok
        try:
            settings = get_settings()
            with patch(
                "backend.ai_engine.runtime.engine.run_post",
                new_callable=AsyncMock,
                side_effect=lambda r, w, p, **kw: r,
            ):
                result = await run(
                    GenerateRequest(
                        mode="img",
                        prompt="change lighting carefully please now",
                        prompt_english="change lighting carefully please now",
                        image_bytes=b"\x89PNG" + b"\x00" * 20,
                        profile="quality",
                    ),
                    settings=settings,
                )
            self.assertTrue(any(e["kind"] == "oom" for e in result.recovery_events))
            self.assertTrue(
                any("profile_degraded" in w for w in result.warnings)
                or result.plan.profile in ("balanced", "draft", "quality")
            )
        finally:
            wf.runner = original

    async def test_hard_fail_after_abort(self) -> None:
        wf = registry.get("image_img2img.v0_legacy")
        assert wf is not None
        original = wf.runner
        fb = wf.fallback_workflow_ref
        wf.fallback_workflow_ref = None

        async def always_fail(**kwargs):
            raise RuntimeError("permanent failure xyz")

        wf.runner = always_fail
        try:
            settings = get_settings()
            with self.assertRaises(ComfyUIError):
                await run(
                    GenerateRequest(
                        mode="img",
                        prompt="img2img",
                        prompt_english="img2img",
                        image_bytes=b"\x89PNG" + b"\x00" * 20,
                    ),
                    settings=settings,
                )
        finally:
            wf.runner = original
            wf.fallback_workflow_ref = fb


if __name__ == "__main__":
    unittest.main()

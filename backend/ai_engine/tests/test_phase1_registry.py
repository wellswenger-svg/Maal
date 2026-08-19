"""Phase 1+2 tests: registry, rules bypass, VLM degrade.

Graphic-intent cases live in gitignored private/tests when present.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.ai_engine.models.catalog import bootstrap_models
from backend.ai_engine.models.manager import manager
from backend.ai_engine.planner import plan
from backend.ai_engine.planner import rules
from backend.ai_engine.planner import vlm
from backend.ai_engine.registry.catalog import bootstrap_workflows
from backend.ai_engine.registry.workflows import registry
from backend.ai_engine.runtime_overlay import attach_private_tests
from backend.ai_engine.schema import GenerateRequest


def _req(prompt: str, mode: str = "img", **kw) -> GenerateRequest:
    return GenerateRequest(
        mode=mode,  # type: ignore[arg-type]
        prompt=prompt,
        prompt_english=prompt,
        image_bytes=b"\x89PNG",
        **kw,
    )


class AiEnginePhase1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bootstrap_models()
        bootstrap_workflows()

    def test_resolve_img_and_vid_legacy(self) -> None:
        img = registry.resolve("image.img2img", channel="stable")
        self.assertEqual(img.workflow_ref, "image_img2img.v0_legacy")
        self.assertTrue(img.enabled)
        vid = registry.resolve("video.i2v", channel="stable")
        self.assertEqual(vid.workflow_ref, "video_i2v.v1")
        self.assertEqual(vid.fallback_workflow_ref, "video_i2v.v0_legacy")

    def test_planner_mode_mapping(self) -> None:
        out = plan.plan(_req("make it sharper and larger"))
        self.assertTrue(out.workflow_ref)

    def test_rules_i2v_keyword(self) -> None:
        r = rules.classify(_req("animate this photo", mode="vid"))
        self.assertEqual(r.task_type, "video.i2v")

    def test_bypass_upscale(self) -> None:
        r = rules.classify(_req("upscale to 4k"))
        self.assertTrue(r.bypass_vlm)

    def test_bypass_bg_remove(self) -> None:
        r = rules.classify(_req("remove the background"))
        self.assertTrue(r.bypass_vlm)

    def test_slot_not_hardcoded_in_vlm_module(self) -> None:
        import inspect

        src = inspect.getsource(vlm)
        self.assertNotIn("planner.default_model", src)


attach_private_tests(globals(), "test_phase1_registry.py")

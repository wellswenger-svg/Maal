"""Keep-outfit reshape: workflow id, mask coverage, no strap subtract on sampler mask."""

from __future__ import annotations

import unittest
from io import BytesIO

from PIL import Image, ImageDraw

from backend.ai_engine.models.catalog import bootstrap_models
from backend.ai_engine.ops.scorecard import WORKFLOW_SCORES
from backend.ai_engine.post.face_lock import (
    _mask_coverage,
    bust_inpaint_mask_png,
    garment_restore_mask,
)
from backend.ai_engine.registry.catalog import bootstrap_workflows
from backend.ai_engine.registry.workflows import registry


class KeepOutfitReshapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bootstrap_models()
        bootstrap_workflows(force=True)

    def test_workflow_registered(self) -> None:
        wf = registry.get("keep_outfit_reshape.v1")
        self.assertIsNotNone(wf)
        self.assertEqual(wf.task_types, ["edit.keep_outfit_reshape"])
        self.assertIn("edit.keep_outfit_reshape", registry.available_task_types(channel="stable"))
        self.assertEqual(WORKFLOW_SCORES["keep_outfit_reshape.v1"], 73)
        self.assertEqual(wf.benchmark_score, 73)

    def test_sampler_mask_coverage_band(self) -> None:
        img = Image.new("RGB", (768, 1024), (80, 60, 50))
        draw = ImageDraw.Draw(img)
        draw.ellipse([240, 40, 520, 360], fill=(210, 170, 150))
        buf = BytesIO()
        img.save(buf, format="PNG")
        mask_png = bust_inpaint_mask_png(buf.getvalue())
        mask = Image.open(BytesIO(mask_png)).convert("L")
        cov = _mask_coverage(mask)
        self.assertGreaterEqual(cov, 0.12)
        self.assertLessEqual(cov, 0.22)

    def test_sampler_mask_not_zeroed_by_strap_guard(self) -> None:
        img = Image.new("RGB", (768, 1024), (80, 60, 50))
        ImageDraw.Draw(img).ellipse([240, 40, 520, 360], fill=(210, 170, 150))
        buf = BytesIO()
        img.save(buf, format="PNG")
        sampler = Image.open(BytesIO(bust_inpaint_mask_png(buf.getvalue()))).convert("L")
        straps = garment_restore_mask(img.size)
        s_arr = list(sampler.getdata())
        g_arr = list(straps.getdata())
        overlap = sum(1 for a, b in zip(s_arr, g_arr) if a > 127 and b > 127)
        # Post restore may overlap edges; sampler must still have a real edit core.
        self.assertGreater(_mask_coverage(sampler), 0.12)
        self.assertGreater(overlap, 0)

    def test_planner_maps_clothed_enhance_to_keep_outfit(self) -> None:
        from backend.ai_engine.planner import plan
        from backend.ai_engine.runtime_overlay import load_private_module
        from backend.ai_engine.schema import GenerateRequest

        if load_private_module("planner_rules") is None:
            self.skipTest("private overlay not installed")
        available = registry.available_task_types(channel="stable")
        req = GenerateRequest(
            mode="img",
            prompt="bigger bust, keep clothes on",
            prompt_english="bigger bust, keep clothes on",
            image_bytes=b"\x00",
        )
        p = plan(req, available_task_types=available)
        self.assertEqual(p.task_type, "edit.keep_outfit_reshape")
        self.assertTrue((p.params_hints or {}).get("clothed_enhance"))


if __name__ == "__main__":
    unittest.main()

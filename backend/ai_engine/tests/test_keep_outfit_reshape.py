"""Keep-outfit reshape: workflow id, garment mask, coverage band."""

from __future__ import annotations

import unittest
from io import BytesIO

from PIL import Image, ImageDraw

from backend.ai_engine.models.catalog import bootstrap_models
from backend.ai_engine.ops.scorecard import WORKFLOW_SCORES
from backend.ai_engine.perception.garment_mask import (
    _local_fabric_mask,
    keep_outfit_edit_mask_png,
)
from backend.ai_engine.post.face_lock import (
    _mask_coverage,
    bust_inpaint_mask_png,
    garment_restore_mask,
)
from backend.ai_engine.registry.catalog import bootstrap_workflows
from backend.ai_engine.registry.workflows import registry


def _portrait_png(size=(768, 1024)) -> bytes:
    img = Image.new("RGB", size, (40, 90, 50))
    draw = ImageDraw.Draw(img)
    draw.ellipse([240, 40, 520, 360], fill=(210, 170, 150))
    draw.rectangle([220, 360, 540, 780], fill=(30, 40, 120))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class KeepOutfitReshapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bootstrap_models()
        bootstrap_workflows(force=True)

    def test_workflow_registered(self) -> None:
        wf = registry.get("keep_outfit_reshape.v1")
        self.assertIsNotNone(wf)
        self.assertEqual(wf.task_types, ["edit.keep_outfit_reshape"])
        self.assertIn(
            "edit.keep_outfit_reshape",
            registry.available_task_types(channel="stable"),
        )
        self.assertEqual(WORKFLOW_SCORES["keep_outfit_reshape.v1"], 73)
        self.assertEqual(wf.benchmark_score, 73)
        deps = (wf.dependencies or {}).get("perception") or []
        self.assertIn("garment", deps)

    def test_sampler_mask_coverage_band(self) -> None:
        mask_png = bust_inpaint_mask_png(_portrait_png(), prefer_comfy=False)
        mask = Image.open(BytesIO(mask_png)).convert("L")
        cov = _mask_coverage(mask)
        self.assertGreaterEqual(cov, 0.12)
        self.assertLessEqual(cov, 0.22)

    def test_garment_intersect_local(self) -> None:
        png = _portrait_png()
        mask_png, meta = keep_outfit_edit_mask_png(png, prefer_comfy=False)
        self.assertEqual(meta.get("garment_source"), "local_fabric")
        cov = _mask_coverage(Image.open(BytesIO(mask_png)).convert("L"))
        self.assertGreaterEqual(cov, 0.12)
        self.assertLessEqual(cov, 0.22)
        local = _local_fabric_mask(Image.open(BytesIO(png)).convert("RGB"))
        self.assertGreater(_mask_coverage(local), 0.05)

    def test_sampler_mask_not_zeroed_by_strap_guard(self) -> None:
        png = _portrait_png()
        img = Image.open(BytesIO(png))
        sampler = Image.open(
            BytesIO(bust_inpaint_mask_png(png, prefer_comfy=False))
        ).convert("L")
        straps = garment_restore_mask(img.size)
        overlap = sum(
            1
            for a, b in zip(sampler.getdata(), straps.getdata())
            if a > 127 and b > 127
        )
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
        self.assertIn("garment", p.perception or [])


if __name__ == "__main__":
    unittest.main()

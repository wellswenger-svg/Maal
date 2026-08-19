"""Phase 4 tests: perception pipeline, grounding/segment heuristics, bg-remove workflow."""

from __future__ import annotations

import asyncio
import unittest
from io import BytesIO
from unittest.mock import patch

from PIL import Image

from backend.ai_engine.models.catalog import bootstrap_models
from backend.ai_engine.models.manager import manager
from backend.ai_engine.perception import grounding, matting, segment
from backend.ai_engine.perception.pipeline import run_perception
from backend.ai_engine.perception.types import BBox
from backend.ai_engine.planner import plan
from backend.ai_engine.registry.catalog import bootstrap_workflows
from backend.ai_engine.registry.workflows import registry
from backend.ai_engine.schema import ExecutionPlan, GenerateRequest
from backend.ai_engine.workflows.background_remove import v1 as bg_remove
from backend.config import get_settings


def _png(w: int = 64, h: int = 64, color=(40, 120, 200)) -> bytes:
    img = Image.new("RGB", (w, h), color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _req(prompt: str, **kw) -> GenerateRequest:
    return GenerateRequest(
        mode="img",
        prompt=prompt,
        prompt_english=prompt,
        image_bytes=_png(),
        **kw,
    )


class FaceViewTests(unittest.TestCase):
    def test_centered_skin_blob_is_full(self) -> None:
        from backend.ai_engine.perception.face_view import classify_face_view

        img = Image.new("RGB", (160, 200), (30, 40, 50))
        # Large centered face-like skin oval
        for y in range(20, 110):
            for x in range(45, 115):
                img.putpixel((x, y), (210, 160, 130))
        buf = BytesIO()
        img.save(buf, format="PNG")
        self.assertEqual(classify_face_view(buf.getvalue()), "full")

    def test_side_skin_blob_is_profile(self) -> None:
        from backend.ai_engine.perception.face_view import classify_face_view

        img = Image.new("RGB", (160, 200), (30, 40, 50))
        for y in range(30, 90):
            for x in range(4, 28):
                img.putpixel((x, y), (210, 160, 130))
        buf = BytesIO()
        img.save(buf, format="PNG")
        self.assertEqual(classify_face_view(buf.getvalue()), "profile")


class PerceptionUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bootstrap_models()
        bootstrap_workflows()

    def test_grounding_heuristic_boxes(self) -> None:
        boxes, warnings = grounding.ground_phrases(_png(), ["shirt"], settings=None)
        self.assertTrue(boxes)
        self.assertIsInstance(boxes[0], BBox)
        self.assertTrue(isinstance(warnings, list))

    def test_segment_from_boxes(self) -> None:
        boxes = [BBox(10, 10, 40, 40, label="shirt", score=0.8)]
        mask = segment.segment_boxes(_png(), boxes, settings=None)
        self.assertGreater(len(mask.mask_png), 50)
        self.assertEqual(mask.width, 64)
        self.assertIn("shirt", mask.labels)

    def test_matting_degrades_without_rembg(self) -> None:
        from unittest.mock import MagicMock

        fake_rembg = MagicMock()
        fake_rembg.remove.side_effect = RuntimeError("forced")
        with patch.dict("sys.modules", {"rembg": fake_rembg}):
            with patch.object(manager, "is_available", return_value=False):
                mask, rgba, warnings = matting.matte_subject(_png(), settings=None)
        self.assertEqual(mask.source, "full_frame")
        self.assertIsNone(rgba)
        self.assertTrue(
            any("rembg" in w or "matting_unavailable" in w for w in warnings)
        )

    def test_pipeline_matting_only(self) -> None:
        p = ExecutionPlan(
            planner_path="rules",
            task_type="image.background_remove",
            confidence=0.95,
            profile="draft",
            prompts={"positive": "remove background"},
            perception=["matting"],
        )
        art = asyncio.run(run_perception(image_bytes=_png(), plan=p, settings=None))
        self.assertIn("matting", art.stages_run)
        self.assertIsNotNone(art.mask)
        self.assertTrue(art.to_meta()["has_mask"])

    def test_pipeline_grounding_sam_degraded(self) -> None:
        p = ExecutionPlan(
            planner_path="rules",
            task_type="edit.clothing_replace",
            confidence=0.9,
            profile="balanced",
            prompts={"positive": "change the shirt to red"},
            targets=[{"label": "shirt"}],
            perception=["grounding", "sam2"],
        )
        art = asyncio.run(run_perception(image_bytes=_png(), plan=p, settings=None))
        self.assertTrue(art.boxes or art.mask)
        self.assertTrue(
            "perception_degraded" in art.warnings
            or "mask_failed" in art.warnings
            or art.mask is not None
        )


class BackgroundRemoveWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bootstrap_models()
        bootstrap_workflows()

    def test_registry_resolves_background_remove(self) -> None:
        wf = registry.resolve("image.background_remove", channel="stable")
        self.assertEqual(wf.workflow_ref, "background_remove.v1")
        self.assertTrue(wf.enabled)
        bind = manager.bind_backbone(wf)
        self.assertIn(bind.model_id, ("matting.rembg", "matting.heuristic", "matting.birefnet", "matting.rmbg2"))

    def test_planner_keeps_background_remove_task(self) -> None:
        available = registry.available_task_types(channel="stable")
        self.assertIn("image.background_remove", available)
        p = plan(_req("remove the background"), available_task_types=available)
        self.assertEqual(p.task_type, "image.background_remove")
        self.assertEqual(p.intent_task_type, "image.background_remove")
        self.assertIn("matting", p.perception)

    def test_runner_returns_png(self) -> None:
        data, ctype, kind, model = asyncio.run(
            bg_remove.run_background_remove(
                image_bytes=_png(),
                prompt="remove background",
                negative=None,
                seed=None,
                settings=get_settings(),
            )
        )
        self.assertEqual(kind, "img")
        self.assertEqual(ctype, "image/png")
        self.assertGreater(len(data), 50)
        self.assertTrue(model.startswith("matting.") or model == "matting.unavailable")

    def test_perception_models_in_catalog(self) -> None:
        for mid in ("grounding.dino", "seg.sam2", "matting.birefnet", "matting.heuristic"):
            self.assertIsNotNone(manager.get(mid), msg=mid)


if __name__ == "__main__":
    unittest.main()

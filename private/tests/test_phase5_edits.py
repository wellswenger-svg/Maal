"""Phase 5 tests: P1 edit registry, prompts, color_match post, planner resolve."""

from __future__ import annotations

import unittest
from io import BytesIO
from unittest.mock import AsyncMock, patch

from PIL import Image, ImageDraw

from backend.ai_engine.models.catalog import bootstrap_models
from backend.ai_engine.models.manager import manager
from backend.ai_engine.planner import plan
from backend.ai_engine.post.pipeline import preserve_outside_mask, run_post
from backend.ai_engine.perception.types import MaskResult, PerceptionArtifacts
from backend.ai_engine.registry.catalog import bootstrap_workflows
from backend.ai_engine.registry.workflows import registry
from backend.ai_engine.schema import EngineResult, ExecutionPlan, GenerateRequest
from backend.ai_engine.workflows._shared.edit_runner import (
    build_edit_prompt,
    pad_for_outpaint,
    simple_upscale,
)


def _png(w: int = 64, h: int = 64, color=(80, 80, 80)) -> bytes:
    img = Image.new("RGB", (w, h), color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _mask_left_half(w: int = 64, h: int = 64) -> bytes:
    m = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(m)
    draw.rectangle([0, 0, w // 2, h], fill=255)
    buf = BytesIO()
    m.save(buf, format="PNG")
    return buf.getvalue()


def _req(prompt: str, **kw) -> GenerateRequest:
    return GenerateRequest(
        mode="img",
        prompt=prompt,
        prompt_english=prompt,
        image_bytes=_png(),
        **kw,
    )


class Phase5RegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bootstrap_models()
        bootstrap_workflows(force=True)

    def test_core_edit_workflows_resolve(self) -> None:
        cases = {
            "edit.clothing_replace": "clothing_replace.v1",
            "edit.object_replace": "object_replace.v1",
            "edit.face": "face_edit.v1",
            "edit.background": "background_replace.v1",
            "edit.inpaint": "inpaint.v1",
            "edit.general_instruction": "instruction_edit.v1",
            "image.upscale": "image_upscale.v1",
            "edit.remove_object": "object_remove.v1",
            "edit.outpaint": "outpaint.v1",
        }
        for task, ref in cases.items():
            wf = registry.resolve(task, channel="stable")
            self.assertEqual(wf.workflow_ref, ref, msg=task)
            self.assertTrue(wf.enabled)
            bind = manager.bind_backbone(wf)
            self.assertTrue(bind.model_id)

    def test_face_swap_beta_not_in_stable(self) -> None:
        available = registry.available_task_types(channel="stable")
        self.assertNotIn("edit.face_swap", available)
        available_beta = registry.available_task_types(channel="stable", allow_beta=True)
        self.assertIn("edit.face_swap", available_beta)

    def test_planner_clothing_keeps_task(self) -> None:
        available = registry.available_task_types(channel="stable")
        p = plan(_req("change the shirt to red"), available_task_types=available)
        self.assertEqual(p.task_type, "edit.clothing_replace")
        self.assertIn("grounding", p.perception)

    def test_planner_face_swap_falls_back_without_beta(self) -> None:
        available = registry.available_task_types(channel="stable")
        # Force classify via direct plan with a swap-like intent by mocking rules
        from backend.ai_engine.planner import rules

        with patch.object(
            rules,
            "classify",
            return_value=rules.RuleResult(
                task_type="edit.face_swap",
                confidence=0.95,
                bypass_vlm=True,
                reason="test",
                perception=["face_detect"],
            ),
        ):
            p = plan(_req("swap the face"), available_task_types=available)
        self.assertEqual(p.intent_task_type, "edit.face_swap")
        self.assertEqual(p.task_type, "edit.face")
        self.assertTrue(any("task_fallback" in w for w in p.warnings))


class Phase5HelperTests(unittest.TestCase):
    def test_build_edit_prompt_clothing(self) -> None:
        text = build_edit_prompt(
            user_prompt="make it blue",
            task_kind="clothing",
            targets=[{"label": "shirt"}],
        )
        self.assertIn("shirt", text.lower())
        self.assertIn("blue", text.lower())

    def test_mask_failed_prefix(self) -> None:
        text = build_edit_prompt(
            user_prompt="fix",
            task_kind="object",
            mask_failed=True,
            raw_prompt=False,
        )
        self.assertIn("mask_failed", text)

    def test_wet_sheer_prompt_requires_visible_change(self) -> None:
        text = build_edit_prompt(
            user_prompt="soak her shirt so it is wet and see-through",
            task_kind="instruction",
            raw_prompt=True,
        ).lower()
        self.assertIn("see through clothes", text)
        self.assertIn("do not output the original dry clothes", text)
        self.assertIn("translucent", text)
        self.assertIn("same color", text)
        self.assertIn("different outfit", text)
        self.assertNotIn("darker, dripping-wet", text)
        self.assertNotIn("black dress", text)

    def test_pose_prompt_keeps_full_face_in_frame(self) -> None:
        text = build_edit_prompt(
            user_prompt="put her bent over on her hands and knees, keep clothes on",
            task_kind="instruction",
            raw_prompt=True,
            face_view="full",
        ).lower()
        self.assertIn("looks back over", text)
        self.assertIn("on all fours", text)
        self.assertIn("both palms", text)
        self.assertIn("torso roughly parallel", text)
        self.assertIn("face stays in frame", text)
        self.assertNotIn("from behind", text)

    def test_pose_prompt_keeps_profile_face_angle(self) -> None:
        text = build_edit_prompt(
            user_prompt="put her bent over on her hands and knees, keep clothes on",
            task_kind="instruction",
            raw_prompt=True,
            face_view="profile",
        ).lower()
        self.assertIn("side", text)
        self.assertIn("do not invent a new frontal face", text)
        self.assertNotIn("full face stays in frame", text)

    def test_fluid_prompt_is_translucent_not_paint(self) -> None:
        text = build_edit_prompt(
            user_prompt="add a facial cumshot of fresh semen on her face",
            task_kind="instruction",
            targets=[{"label": "face"}],
            raw_prompt=True,
        ).lower()
        self.assertIn("slimy translucent", text)
        self.assertIn("skin and facial features show through", text)
        self.assertIn("never flat matte opaque white paint", text)
        self.assertIn("specular", text)
        self.assertIn("chest/clothes", text)
        self.assertNotIn("ivory", text)
        self.assertNotIn("pearlescent", text)
        self.assertNotIn("visible fluid overlay", text)

    def test_raw_prompt_passes_user_text(self) -> None:
        text = build_edit_prompt(
            user_prompt="make the jacket leather and open",
            task_kind="clothing",
            targets=[{"label": "jacket"}],
            raw_prompt=True,
        )
        self.assertIn("leather", text.lower())
        self.assertNotIn("preserve identity", text.lower())
        self.assertNotIn("unchanged", text.lower())

    def test_outpaint_pad_grows(self) -> None:
        out = pad_for_outpaint(_png(64, 64))
        img = Image.open(BytesIO(out))
        self.assertGreater(img.width, 64)
        self.assertGreater(img.height, 64)

    def test_simple_upscale(self) -> None:
        out = simple_upscale(_png(32, 32), 2.0)
        img = Image.open(BytesIO(out))
        self.assertEqual(img.size, (64, 64))

    def test_fluid_recolor_turns_white_paint_cream_grey(self) -> None:
        from backend.ai_engine.post.fluid_recolor import recolor_white_paint_to_gel

        skin = Image.new("RGB", (64, 64), (160, 110, 90))
        painted = skin.copy()
        ImageDraw.Draw(painted).rectangle([16, 16, 48, 48], fill=(255, 255, 255))
        ob = BytesIO()
        skin.save(ob, format="PNG")
        eb = BytesIO()
        painted.save(eb, format="PNG")
        out = Image.open(BytesIO(recolor_white_paint_to_gel(ob.getvalue(), eb.getvalue()))).convert("RGB")
        mid = out.getpixel((32, 32))
        edge = out.getpixel((2, 2))
        # Face translucency: mid should pull toward skin, not stay chalk white.
        self.assertLess(mid[0], 245)
        self.assertGreater(mid[0], 150)
        self.assertLess(sum(abs(a - b) for a, b in zip(edge, (160, 110, 90))), 12)

    def test_fluid_recolor_face_only_keeps_clothes_drips(self) -> None:
        from backend.ai_engine.post.fluid_recolor import recolor_white_paint_to_gel

        skin = Image.new("RGB", (96, 128), (160, 110, 90))
        painted = skin.copy()
        draw = ImageDraw.Draw(painted)
        draw.ellipse([28, 18, 68, 58], fill=(255, 255, 255))  # face blob
        draw.rectangle([30, 95, 66, 120], fill=(220, 220, 220))  # clothes drip
        ob = BytesIO()
        skin.save(ob, format="PNG")
        eb = BytesIO()
        painted.save(eb, format="PNG")
        out = Image.open(
            BytesIO(
                recolor_white_paint_to_gel(
                    ob.getvalue(), eb.getvalue(), face_only=True
                )
            )
        ).convert("RGB")
        face = out.getpixel((48, 38))
        chest = out.getpixel((48, 108))
        # Face should show skin through (not ~255 paint).
        self.assertLess(face[0], 245)
        # Clothes drip should remain visibly lighter than skin (not fully restored).
        self.assertGreater(chest[0], 170)

    def test_fluid_recolor_restores_melted_hair_strands(self) -> None:
        from backend.ai_engine.post.fluid_recolor import recolor_white_paint_to_gel

        orig = Image.new("RGB", (64, 64), (160, 110, 90))
        draw = ImageDraw.Draw(orig)
        draw.rectangle([0, 0, 64, 28], fill=(22, 16, 14))
        painted = orig.copy()
        pd = ImageDraw.Draw(painted)
        pd.rectangle([6, 2, 58, 24], fill=(150, 155, 165))
        ob = BytesIO()
        orig.save(ob, format="PNG")
        eb = BytesIO()
        painted.save(eb, format="PNG")
        out = Image.open(
            BytesIO(recolor_white_paint_to_gel(ob.getvalue(), eb.getvalue()))
        ).convert("RGB")
        hair = out.getpixel((32, 12))
        self.assertLess(hair[0], 80)

    def test_fluid_recolor_restores_dulled_hair_color(self) -> None:
        from backend.ai_engine.post.fluid_recolor import recolor_white_paint_to_gel

        orig = Image.new("RGB", (64, 64), (160, 110, 90))
        draw = ImageDraw.Draw(orig)
        draw.rectangle([0, 0, 64, 28], fill=(48, 32, 24))
        painted = orig.copy()
        pd = ImageDraw.Draw(painted)
        pd.rectangle([6, 2, 58, 24], fill=(88, 90, 92))
        ob = BytesIO()
        orig.save(ob, format="PNG")
        eb = BytesIO()
        painted.save(eb, format="PNG")
        out = Image.open(
            BytesIO(recolor_white_paint_to_gel(ob.getvalue(), eb.getvalue()))
        ).convert("RGB")
        hair = out.getpixel((32, 12))
        self.assertGreater(hair[0], hair[2] + 4)
        self.assertLess(abs(hair[0] - 48), 18)

    def test_preserve_outside_mask(self) -> None:
        orig = _png(64, 64, (10, 10, 10))
        edited = _png(64, 64, (200, 200, 200))
        mask = _mask_left_half(64, 64)
        blended = preserve_outside_mask(orig, edited, mask)
        img = Image.open(BytesIO(blended)).convert("RGB")
        # Left (masked) should be near edited bright; right near original dark
        left = img.getpixel((10, 32))
        right = img.getpixel((50, 32))
        self.assertGreater(sum(left), 400)
        self.assertLess(sum(right), 100)

    def test_face_lock_restores_original_face_pixels(self) -> None:
        from backend.ai_engine.post.face_lock import restore_original_face

        orig = Image.new("RGB", (64, 128), (20, 180, 20))
        ImageDraw.Draw(orig).rectangle([14, 4, 50, 44], fill=(210, 40, 40))
        edited = Image.new("RGB", (64, 128), (30, 30, 210))
        ob, eb = BytesIO(), BytesIO()
        orig.save(ob, format="PNG")
        edited.save(eb, format="PNG")
        with patch(
            "backend.ai_engine.post.face_lock.detect_face_box",
            return_value=(14, 4, 36, 40),
        ):
            out = Image.open(
                BytesIO(restore_original_face(ob.getvalue(), eb.getvalue()))
            ).convert("RGB")
        face = out.getpixel((32, 22))
        chest = out.getpixel((32, 96))
        self.assertGreater(face[0], 150)
        self.assertLess(face[2], 80)
        self.assertGreater(chest[2], 150)
        self.assertLess(chest[0], 80)


class Phase5PostTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bootstrap_models()
        bootstrap_workflows(force=True)

    async def test_color_match_applied(self) -> None:
        wf = registry.get("clothing_replace.v1")
        assert wf is not None
        plan = ExecutionPlan(
            planner_path="rules",
            task_type="edit.clothing_replace",
            confidence=0.9,
            profile="balanced",
        )
        perception = PerceptionArtifacts(
            mask=MaskResult(
                mask_png=_mask_left_half(),
                width=64,
                height=64,
                source="grounding+sam2",
            )
        )
        result = EngineResult(
            data=_png(64, 64, (255, 0, 0)),
            content_type="image/png",
            kind="img",
            model_label="test",
            workflow_ref=wf.workflow_ref,
            plan=plan,
        )
        out = await run_post(
            result,
            wf,
            plan,
            original_bytes=_png(64, 64, (0, 0, 255)),
            perception=perception,
        )
        self.assertTrue(any("post_applied:color_match" in w for w in out.warnings))

    async def test_clothed_face_lock_applied(self) -> None:
        wf = registry.get("instruction_edit.v1")
        assert wf is not None
        orig = Image.new("RGB", (64, 128), (20, 180, 20))
        ImageDraw.Draw(orig).rectangle([14, 4, 50, 44], fill=(210, 40, 40))
        edited = Image.new("RGB", (64, 128), (30, 30, 210))
        ob, eb = BytesIO(), BytesIO()
        orig.save(ob, format="PNG")
        edited.save(eb, format="PNG")
        plan = ExecutionPlan(
            planner_path="rules",
            task_type="edit.general_instruction",
            confidence=0.92,
            profile="quality",
            post_hints=["face_detailer"],
            targets=[{"label": "cleavage", "role": "reshape_region"}],
            params_hints={"clothed_enhance": True},
        )
        result = EngineResult(
            data=eb.getvalue(),
            content_type="image/png",
            kind="img",
            model_label="backbone.flux_kontext_dev_fp8|clothed_i2i",
            workflow_ref=wf.workflow_ref,
            plan=plan,
        )
        with patch(
            "backend.ai_engine.post.face_lock.detect_face_box",
            return_value=(14, 4, 36, 40),
        ):
            out = await run_post(
                result,
                wf,
                plan,
                original_bytes=ob.getvalue(),
            )
        joined = " ".join(out.warnings)
        self.assertIn("face_lock", joined)
        self.assertIn("chest_lock", joined)
        img = Image.open(BytesIO(out.data)).convert("RGB")
        # Face / sleeves / hem / corners stay original; only the bust core may change.
        self.assertGreater(img.getpixel((32, 18))[0], 150)
        self.assertEqual(img.getpixel((2, 2)), (20, 180, 20))
        self.assertEqual(img.getpixel((62, 126)), (20, 180, 20))
        self.assertGreater(img.getpixel((4, 64))[1], 140)
        self.assertGreater(img.getpixel((32, 120))[1], 140)

    def test_chest_lock_keeps_edit_only_on_bust(self) -> None:
        from backend.ai_engine.post.face_lock import restore_outside_chest

        orig = Image.new("RGB", (64, 128), (20, 180, 20))
        ImageDraw.Draw(orig).rectangle([14, 4, 50, 44], fill=(210, 40, 40))
        edited = Image.new("RGB", (64, 128), (30, 30, 210))
        ob, eb = BytesIO(), BytesIO()
        orig.save(ob, format="PNG")
        edited.save(eb, format="PNG")
        out = Image.open(
            BytesIO(restore_outside_chest(ob.getvalue(), eb.getvalue()))
        ).convert("RGB")
        face = out.getpixel((32, 18))
        hem = out.getpixel((32, 118))
        hand = out.getpixel((10, 56))
        corner = out.getpixel((2, 2))
        self.assertGreater(face[0], 150)
        self.assertEqual(corner, (20, 180, 20))
        self.assertGreater(hem[1], 140)
        self.assertGreater(hand[1], 140)
        self.assertEqual(out.getpixel((62, 126)), (20, 180, 20))

    def test_chest_lock_copies_start_photo_outside_bust(self) -> None:
        from backend.ai_engine.post.face_lock import restore_outside_chest

        orig = Image.new("RGB", (64, 128), (11, 22, 33))
        ImageDraw.Draw(orig).rectangle([18, 6, 46, 40], fill=(200, 30, 30))
        edited = Image.new("RGB", (64, 128), (255, 220, 0))
        ob, eb = BytesIO(), BytesIO()
        orig.save(ob, format="PNG")
        edited.save(eb, format="PNG")
        out = Image.open(
            BytesIO(restore_outside_chest(ob.getvalue(), eb.getvalue()))
        ).convert("RGB")
        for xy in ((1, 1), (62, 1), (1, 126), (62, 126), (8, 70), (56, 70), (32, 110)):
            self.assertEqual(out.getpixel(xy), (11, 22, 33), msg=xy)


class ClothedEnhancePathTests(unittest.IsolatedAsyncioTestCase):
    async def test_clothed_sizeup_uses_img2img_not_kontext(self) -> None:
        from backend.ai_engine.schema import ModelBindResult
        from backend.ai_engine.workflows._shared.edit_runner import run_flux_edit
        from backend.config import Settings

        captured: dict = {}

        class _Client:
            async def generate_image(self, *args, **kwargs):
                captured.update(kwargs)
                return b"png", "image/png"

        plan = ExecutionPlan(
            planner_path="rules",
            task_type="edit.general_instruction",
            confidence=0.92,
            targets=[{"label": "cleavage", "role": "reshape_region"}],
            params_hints={
                "loras": ["nsfw_unlock", "breast_enhance"],
                "nsfw_edit": True,
                "clothed_enhance": True,
                "denoise": 0.84,
            },
        )
        settings = Settings.model_construct(
            mongodb_uri="mongodb://localhost",
            raw_prompt=True,
            image_denoise=0.55,
            image_denoise_cap=0.85,
        )
        backbone = ModelBindResult(
            model_id="backbone.flux_kontext_dev_fp8",
            tier="preferred",
            filename="flux1-dev-kontext_fp8_scaled.safetensors",
        )
        prompt = (
            "huge natural breasts under clothes keep clothes on, "
            "make her bust larger with more cleavage"
        )
        with patch(
            "backend.ai_engine.workflows._shared.edit_runner.ComfyClient",
            return_value=_Client(),
        ), patch(
            "backend.ai_engine.workflows._shared.edit_runner._lora_available",
            return_value=True,
        ):
            _data, _ct, _kind, label = await run_flux_edit(
                image_bytes=_png(),
                prompt=prompt,
                negative=None,
                seed=1,
                settings=settings,
                plan=plan,
                backbone=backbone,
                task_kind="instruction",
            )
        self.assertEqual(captured.get("edit_graph"), "img2img")
        self.assertTrue(captured.get("wrap_preserve"))
        self.assertIn("clothed_i2i", label)
        self.assertIn("clothed_enhance_cap", label)
        self.assertIn("chest_inpaint", label)
        self.assertTrue(captured.get("mask_bytes"))
        self.assertGreaterEqual(float(captured.get("denoise") or 0), 0.80)
        self.assertLessEqual(float(captured.get("denoise") or 1), 0.86)
        neg = (captured.get("negative") or "").lower()
        self.assertIn("nipples visible", neg)
        self.assertIn("breasts above the neckline", neg)
        self.assertIn("warped torso", neg)
        self.assertIn("recolored shirt", neg)
        self.assertIn("warped background", neg)
        self.assertIn("yellow stain", neg)

    async def test_no_sheer_negation_does_not_load_see_through(self) -> None:
        from backend.ai_engine.schema import ModelBindResult
        from backend.ai_engine.workflows._shared.edit_runner import run_flux_edit
        from backend.config import Settings

        captured: dict = {}

        class _Client:
            async def generate_image(self, *args, **kwargs):
                captured.update(kwargs)
                return b"png", "image/png"

        plan = ExecutionPlan(
            planner_path="rules",
            task_type="edit.general_instruction",
            confidence=0.92,
            targets=[{"label": "cleavage", "role": "reshape_region"}],
            params_hints={
                "loras": ["nsfw_unlock", "breast_enhance"],
                "nsfw_edit": True,
                "clothed_enhance": True,
                "denoise": 0.84,
            },
        )
        settings = Settings.model_construct(
            mongodb_uri="mongodb://localhost",
            raw_prompt=True,
            image_denoise=0.55,
            image_denoise_cap=0.85,
        )
        backbone = ModelBindResult(
            model_id="backbone.flux_kontext_dev_fp8",
            tier="preferred",
            filename="flux1-dev-kontext_fp8_scaled.safetensors",
        )
        prompt = (
            "huge natural breasts under clothes keep clothes on, "
            "make her bust larger with more cleavage. "
            "No nipples, no areola, no poke-through, no sheer fabric."
        )
        with patch(
            "backend.ai_engine.workflows._shared.edit_runner.ComfyClient",
            return_value=_Client(),
        ), patch(
            "backend.ai_engine.workflows._shared.edit_runner._lora_available",
            return_value=True,
        ):
            _data, _ct, _kind, label = await run_flux_edit(
                image_bytes=_png(),
                prompt=prompt,
                negative=None,
                seed=1,
                settings=settings,
                plan=plan,
                backbone=backbone,
                task_kind="instruction",
            )
        self.assertIn("clothed_i2i", label)
        self.assertNotIn("wet_sheer", label.lower())
        names = " ".join(str(x) for x in (captured.get("loras") or [])).lower()
        self.assertNotIn("see_through", names)
        self.assertNotIn("wet_shirt", names)
        self.assertEqual(captured.get("edit_graph"), "img2img")

    def test_no_sheer_clothed_prompt_does_not_wrap_as_wet(self) -> None:
        text = build_edit_prompt(
            user_prompt=(
                "huge natural breasts under clothes keep clothes on, "
                "make her bust larger. No nipples, no sheer fabric."
            ),
            task_kind="instruction",
            targets=[{"label": "cleavage"}],
            raw_prompt=True,
        ).lower()
        self.assertNotIn("see through clothes", text)
        self.assertNotIn("do not make the cloth opaque", text)
        self.assertIn("cloth stays opaque", text)

    def test_clothed_prompt_keeps_neckline_in_place(self) -> None:
        text = build_edit_prompt(
            user_prompt="huge natural breasts under clothes, keep clothes on",
            task_kind="instruction",
            targets=[{"label": "cleavage"}],
            raw_prompt=True,
        ).lower()
        self.assertIn("same neckline", text)
        self.assertIn("inside the current collar", text)
        self.assertIn("do not expose nipples", text)


if __name__ == "__main__":
    unittest.main()

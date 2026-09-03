"""Phase 1+2 tests: registry, rules bypass, VLM degrade (no ComfyUI / no GPU VLM required)."""

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
        # Phase 6: v1 preferred over v0_legacy by version rank
        self.assertEqual(vid.workflow_ref, "video_i2v.v1")
        self.assertEqual(vid.fallback_workflow_ref, "video_i2v.v0_legacy")

    def test_disabled_workflow_not_resolved(self) -> None:
        rec = registry.get("image_img2img.v0_legacy")
        assert rec is not None
        prev = rec.enabled
        try:
            rec.enabled = False
            with self.assertRaises(KeyError):
                registry.resolve("image.img2img", channel="stable")
        finally:
            rec.enabled = prev

    def test_planner_mode_mapping(self) -> None:
        available = registry.available_task_types(channel="stable")
        img_plan = plan(_req("change the lighting slightly"), available_task_types=available)
        # Ambiguous / general edits resolve to instruction_edit when available
        self.assertIn(img_plan.task_type, ("image.img2img", "edit.general_instruction"))
        self.assertEqual(img_plan.planner_path, "rules")

        vid_plan = plan(_req("subtle smile", mode="vid"), available_task_types=available)
        self.assertEqual(vid_plan.task_type, "video.i2v")

    def test_upscale_keyword_resolves_when_workflow_exists(self) -> None:
        available = registry.available_task_types(channel="stable")
        p = plan(_req("upscale to 4k"), available_task_types=available)
        self.assertEqual(p.intent_task_type, "image.upscale")
        self.assertEqual(p.task_type, "image.upscale")
        self.assertFalse(any(w.startswith("task_fallback:") for w in p.warnings))

    def test_rules_i2v_keyword(self) -> None:
        task, conf, _ = rules.classify_task_type(_req("animate this photo"))
        self.assertEqual(task, "video.i2v")
        self.assertGreaterEqual(conf, 0.9)

    def test_planner_default_model_slot(self) -> None:
        slot = manager.resolve_slot("planner.default_model")
        self.assertEqual(slot.model_id, "vlm.qwen25_vl_7b")

    def test_bind_backbone_preferred(self) -> None:
        wf = registry.resolve("image.img2img")
        bind = manager.bind_backbone(wf)
        self.assertEqual(bind.model_id, "backbone.flux_dev_fp8")
        self.assertEqual(bind.tier, "preferred")


class AiEnginePhase2RulesTests(unittest.TestCase):
    def test_bypass_upscale(self) -> None:
        r = rules.classify(_req("please upscale this image"))
        self.assertEqual(r.task_type, "image.upscale")
        self.assertTrue(r.bypass_vlm)
        self.assertGreaterEqual(r.confidence, 0.9)

    def test_bypass_bg_remove(self) -> None:
        r = rules.classify(_req("remove the background"))
        self.assertEqual(r.task_type, "image.background_remove")
        self.assertTrue(r.bypass_vlm)

    def test_bypass_img2vid(self) -> None:
        r = rules.classify(_req("make a video from this"))
        self.assertEqual(r.task_type, "video.i2v")
        self.assertTrue(r.bypass_vlm)

    def test_clothing_replace(self) -> None:
        r = rules.classify(_req("change the shirt to red"))
        self.assertEqual(r.task_type, "edit.clothing_replace")
        self.assertTrue(r.bypass_vlm)
        self.assertTrue(r.targets)

    def test_ambiguous_needs_vlm(self) -> None:
        r = rules.classify(_req("fix it"))
        self.assertFalse(r.bypass_vlm)
        self.assertLess(r.confidence, rules.RULE_CONFIDENCE_THRESHOLD)

    def test_face_edit(self) -> None:
        r = rules.classify(_req("make her smile naturally"))
        self.assertEqual(r.task_type, "edit.face")
        self.assertTrue(r.bypass_vlm)

    def test_fluid_overlay_face(self) -> None:
        r = rules.classify(_req("add a cumshot on her face"))
        self.assertEqual(r.task_type, "edit.general_instruction")
        self.assertTrue(r.bypass_vlm)
        self.assertTrue(r.params_hints.get("fluid_edit"))
        self.assertFalse(r.params_hints.get("undress_fluid"))
        self.assertIn("nsfw_unlock", r.params_hints.get("loras") or [])
        self.assertIn("cof", r.params_hints.get("loras") or [])
        self.assertEqual(r.targets[0]["label"], "face")
        self.assertLessEqual(float(r.params_hints.get("denoise") or 1), 0.62)

    def test_fluid_overlay_glasses(self) -> None:
        r = rules.classify(_req("put cum on her glasses and specs"))
        self.assertEqual(r.task_type, "edit.general_instruction")
        self.assertEqual(r.targets[0]["label"], "glasses")
        self.assertNotIn("clothes_remover", r.params_hints.get("loras") or [])

    def test_fluid_overlay_lips_not_face_edit(self) -> None:
        r = rules.classify(_req("cum on her lips"))
        self.assertEqual(r.task_type, "edit.general_instruction")
        self.assertEqual(r.targets[0]["label"], "lips")

    def test_fluid_overlay_hair(self) -> None:
        r = rules.classify(_req("cumshot in her hair"))
        self.assertEqual(r.task_type, "edit.general_instruction")
        self.assertEqual(r.targets[0]["label"], "hair")

    def test_cumshot_lips_preset_targets_lips(self) -> None:
        prompt = (
            "Photorealistic edit of the exact woman in the start image. "
            "CRITICAL: keep her exact same face geometry, eyes, eyebrows, nose, jaw, "
            "skin tone, age, hair, body, clothes, pose, framing, lighting, and background. "
            "Do not remake or replace her. "
            "Only change this: put realistic fresh semen on her lips and mouth only — "
            "whitish translucent cum is splattered as shallow cream-grey opalescent gooey "
            "droplets, thin film, lip color still showing through, uneven beads and a wet sheen, "
            "without covering cheeks or forehead. "
            "Not paint, not makeup, not a solid blob, not a uniform coat. "
            "Keep her clothes on. Do not undress her. Crisp focus, high detail fluids."
        )
        r = rules.classify(_req(prompt))
        self.assertEqual(r.reason, "fluid_overlay_pattern")
        self.assertEqual(r.targets[0]["label"], "lips")
        self.assertIn("nsfw_unlock", r.params_hints.get("loras") or [])
        self.assertIn("cof", r.params_hints.get("loras") or [])
        self.assertFalse(r.params_hints.get("undress_fluid"))

    def test_cumshot_glasses_preset_targets_glasses(self) -> None:
        prompt = (
            "Photorealistic edit of the exact woman in the start image. "
            "CRITICAL: keep her exact same face geometry, eyes, eyebrows, nose, lip shape, "
            "jaw, skin tone, age, hair, body, clothes, pose, framing, lighting, and background. "
            "Do not remake or replace her. "
            "Only change this: put realistic fresh semen on her glasses and lenses only — "
            "whitish translucent cum is splattered as shallow cream-grey opalescent droplets "
            "and thin watery streaks, glass still readable through the film, uneven not a "
            "uniform smear. "
            "Not paint, not opaque blobs. If she is not wearing glasses, keep the edit "
            "subtle on the eyewear area only. "
            "Keep her clothes on. Do not undress her. Crisp focus, high detail fluids."
        )
        r = rules.classify(_req(prompt))
        self.assertEqual(r.reason, "fluid_overlay_pattern")
        self.assertEqual(r.targets[0]["label"], "glasses")
        self.assertIn("nsfw_unlock", r.params_hints.get("loras") or [])
        self.assertIn("cof", r.params_hints.get("loras") or [])
        self.assertNotIn("clothes_remover", r.params_hints.get("loras") or [])

    def test_pose_all_fours_clothed_preset(self) -> None:
        prompt = (
            "Photorealistic edit of the exact woman in the start image. "
            "CRITICAL: keep her exact same face, hair, skin tone, body proportions, identity, "
            "outfit, fabric, color, and clothing coverage. Keep her clothes on. Do not undress. "
            "Do not make her nude or topless. "
            "Only change this: put her on all fours — both palms and both knees on the floor, "
            "torso parallel to the ground, hips raised, ass up, full body in frame, natural matching body. "
            "Keep her face visible — 3/4 camera, looking back over her shoulder; do not hide her face, "
            "do not show only the back of her head, do not crop to a seated portrait. "
            "Same background and lighting. Crisp focus, realistic cloth folds, no face morphing, no extra people."
        )
        r = rules.classify(_req(prompt))
        self.assertEqual(r.reason, "pose_rear_clothed_pattern")
        self.assertTrue(r.params_hints.get("pose_edit"))
        self.assertFalse(r.params_hints.get("pose_undress"))
        self.assertEqual(r.params_hints.get("loras"), ["nsfw_unlock"])
        self.assertNotIn("clothes_remover", r.params_hints.get("loras") or [])

    def test_pose_all_fours_nude_preset(self) -> None:
        prompt = (
            "Photorealistic edit of the exact woman in the start image. "
            "CRITICAL: keep her exact same face, hair, skin tone, body proportions, and identity. "
            "Do not remake or replace her face. "
            "Remove all clothing so she is fully nude. Put her on all fours — both palms and both "
            "knees on the floor, torso parallel to the ground, hips raised, ass up, full body in frame, "
            "natural bare breasts and realistic female anatomy matching her start-image body. "
            "Keep her face visible — 3/4 camera, looking back over her shoulder; do not hide her face, "
            "do not show only the back of her head, do not crop to a seated portrait. "
            "Same background and lighting as the start image. Crisp focus, high detail skin, "
            "no face morphing, no extra people."
        )
        r = rules.classify(_req(prompt))
        self.assertEqual(r.reason, "pose_rear_undress_pattern")
        self.assertTrue(r.params_hints.get("pose_edit"))
        self.assertTrue(r.params_hints.get("pose_undress"))
        self.assertIn("clothes_remover", r.params_hints.get("loras") or [])
        self.assertIn("nsfw_unlock", r.params_hints.get("loras") or [])
        self.assertEqual(r.targets[0]["label"], "body")

    def test_wet_sheer_shirt_preset(self) -> None:
        prompt = (
            "Photorealistic edit of the exact woman in the start image. Keep her exact face, "
            "hair, identity, pose, framing, and background. "
            "Keep the SAME shirt/top ON her body — same color, same cut, same neckline, same sleeves. "
            "Do not take it off. Do not change it into a different outfit. "
            "REQUIRED: wet clothes, see through clothes, transparent clothes. Soak THIS garment so it "
            "clings to her chest with shiny water highlights, fabric turned translucent so breast "
            "shape and nipples clearly show through the wet material. "
            "The dry shirt must look obviously wet and sheer, not the original dry clothes. "
            "Do not return an unchanged photo. "
            "Crisp focus, realistic wet fabric, no face morphing."
        )
        r = rules.classify(_req(prompt))
        self.assertEqual(r.reason, "wet_sheer_shirt_pattern")
        self.assertTrue(r.params_hints.get("wet_sheer"))
        self.assertIn("nsfw_unlock", r.params_hints.get("loras") or [])
        self.assertIn("see_through", r.params_hints.get("loras") or [])
        self.assertIn("wet_shirt", r.params_hints.get("loras") or [])
        self.assertNotIn("clothes_remover", r.params_hints.get("loras") or [])
        self.assertNotEqual(r.reason, "undress_nsfw_pattern")
        self.assertEqual(r.targets[0]["label"], "shirt")

    def test_no_sheer_negation_stays_clothed_not_wet(self) -> None:
        r = rules.classify(
            _req(
                "make her bust larger keep clothes on. "
                "No nipples, no areola, no poke-through, no sheer fabric."
            )
        )
        self.assertEqual(r.reason, "clothed_body_enhance_pattern")
        self.assertTrue(r.params_hints.get("clothed_enhance"))
        self.assertFalse(r.params_hints.get("wet_sheer"))
        self.assertNotIn("see_through", r.params_hints.get("loras") or [])

    def test_cumshot_clothes_preset_keeps_clothes(self) -> None:
        prompt = (
            "Photorealistic edit of the exact woman in the start image. "
            "CRITICAL identity lock: keep her exact same face geometry, eyes, eyebrows, "
            "nose, lip shape, jaw, skin pores, freckles, hair, body, pose, framing, "
            "lighting, and background. Do not remake, beautify, blur, or replace her face "
            "— her face must stay fully recognizable through the fluid. "
            "Add realistic fresh semen: slimy translucent whitish gel — cream-white, gooey, "
            "stringy, wet — uneven ropes and splatters on her face (forehead, cheeks, nose, "
            "lips, chin) with sticky drips, and natural uneven drips on her chest and "
            "clothes too. "
            "Material is the key: translucent slimy semen so skin tone and facial features "
            "show through thinner films; thicker beads are cloudier but still gel not paint. "
            "Bright wet specular highlights. Irregular blotchy edges, mixed thickness, "
            "stringy strands — never a flat matte opaque white paint patch, never acrylic, "
            "never chalk, never toothpaste, never a solid mask hiding her face. "
            "Keep her clothes on (do not undress). Clothes may get uneven translucent drips "
            "for a natural look. Crisp focus, high detail wet gel and skin."
        )
        r = rules.classify(_req(prompt))
        self.assertEqual(r.reason, "fluid_overlay_pattern")
        self.assertTrue(r.params_hints.get("fluid_edit"))
        self.assertFalse(r.params_hints.get("undress_fluid"))
        self.assertIn("nsfw_unlock", r.params_hints.get("loras") or [])
        self.assertIn("cof", r.params_hints.get("loras") or [])
        self.assertNotIn("clothes_remover", r.params_hints.get("loras") or [])
        self.assertEqual(r.targets[0]["label"], "face")

    def test_cumshot_nude_preset_undress_and_drench(self) -> None:
        prompt = (
            "Photorealistic edit of the exact woman in the start image. "
            "CRITICAL: keep her exact same face geometry — same eyes, eyebrows, nose, "
            "lip shape, jaw, skin tone, age, hair, body proportions, and identity. "
            "Do not remake, beautify, or replace her face. "
            "Remove all clothing so she is fully nude. Natural bare breasts and realistic "
            "female anatomy. Same pose, framing, lighting, and background as the start image. "
            "Cover her nude body in a heavy cumshot of realistic semen: whitish translucent "
            "cum is splattered — cream-grey opalescent, gooey, stringy, wet, not opaque white. "
            "Irregular pools, sticky strings, and beads of uneven thickness across "
            "face, neck, breasts, stomach, and thighs. "
            "Bare skin stays visible through thinner films; some spots cloudier gel, some "
            "watery see-through streaks; wet gloss — never a uniform sheet or solid paint "
            "coat. If she wears glasses, shallow translucent drips on the lenses too. "
            "Crisp focus, high detail fluids and skin, no blur, no face morphing."
        )
        r = rules.classify(_req(prompt))
        self.assertEqual(r.reason, "fluid_undress_overlay_pattern")
        self.assertTrue(r.params_hints.get("fluid_edit"))
        self.assertTrue(r.params_hints.get("undress_fluid"))
        self.assertIn("clothes_remover", r.params_hints.get("loras") or [])
        self.assertIn("nsfw_unlock", r.params_hints.get("loras") or [])
        self.assertIn("cof", r.params_hints.get("loras") or [])
        self.assertEqual(r.targets[0]["label"], "body")
        self.assertGreaterEqual(float(r.params_hints.get("denoise") or 0), 0.9)

    def test_clothed_breast_enhance_not_undress(self) -> None:
        r = rules.classify(_req("enhance boob size and cleavage while clothed"))
        self.assertEqual(r.task_type, "edit.general_instruction")
        self.assertTrue(r.params_hints.get("clothed_enhance"))
        self.assertNotIn("clothes_remover", r.params_hints.get("loras") or [])
        self.assertEqual(r.targets[0]["label"], "cleavage")
        self.assertIn("breast_enhance", r.params_hints.get("loras") or [])

    def test_clothed_ass_enhance(self) -> None:
        r = rules.classify(_req("make her ass bigger keep clothes on"))
        self.assertTrue(r.params_hints.get("clothed_enhance"))
        self.assertEqual(r.targets[0]["label"], "ass")
        self.assertNotEqual(r.reason, "undress_nsfw_pattern")

    def test_enhance_boobs_preset_targets_cleavage(self) -> None:
        prompt = (
            "Photorealistic edit of the exact woman in the start image. "
            "CRITICAL: keep her exact same face, hair, pose, framing, lighting, background, "
            "and the SAME clothes fully on — same outfit, fabric, color, and coverage. "
            "Do not undress. Do not make her nude or topless. Do not change her ass or hips. "
            "Only change this: make her bust obviously larger and fuller so the size-up is "
            "easy to see. Keep every breast fully covered by the same shirt — if the bigger "
            "chest would overflow, extend and stretch that same fabric naturally so it still "
            "covers. Show a cleavage line at the existing collar under the cloth. "
            "Crisp focus, realistic cloth folds, no face morphing."
        )
        r = rules.classify(_req(prompt))
        self.assertEqual(r.reason, "clothed_body_enhance_pattern")
        self.assertTrue(r.params_hints.get("clothed_enhance"))
        self.assertEqual(r.targets[0]["label"], "cleavage")
        self.assertEqual(r.params_hints.get("loras"), ["nsfw_unlock", "breast_enhance"])
        self.assertNotIn("clothes_remover", r.params_hints.get("loras") or [])
        self.assertAlmostEqual(float(r.params_hints.get("denoise") or 0), 0.84)

    def test_enhance_boobs_live_preset_stays_clothed(self) -> None:
        prompt = (
            "Photorealistic edit of the exact woman in the start image. "
            "CRITICAL: keep her exact same face, hair, pose, framing, lighting, background, "
            "and the SAME top ON — same outfit, fabric, color, cut, and neckline position. "
            "Do not undress. Do not make her nude or topless. Do not change her ass or hips. "
            "Keep any object in her hand unchanged. "
            "Only change this: huge natural breasts under clothes, shirt covering chest. "
            "Make her bust two cup sizes larger than the start image — an obvious size-up, "
            "rounder and heavier, pushed together with a deep cleavage crease filling the "
            "existing neckline. Keep the neckline where it is; stretch the same fabric over "
            "the larger bust so both breasts stay fully inside the garment. "
            "Do not extend breasts above the collar, do not rest breasts on top of the shirt, "
            "do not show nipples, do not go topless, do not change into a different outfit. "
            "Crisp focus, realistic cloth folds, no face morphing."
        )
        r = rules.classify(_req(prompt))
        self.assertEqual(r.reason, "clothed_body_enhance_pattern")
        self.assertTrue(r.params_hints.get("clothed_enhance"))
        self.assertEqual(r.targets[0]["label"], "cleavage")
        self.assertNotIn("clothes_remover", r.params_hints.get("loras") or [])
        self.assertIn("breast_enhance", r.params_hints.get("loras") or [])

    def test_enhance_boobs_extend_fabric_stays_clothed(self) -> None:
        r = rules.classify(
            _req(
                "make her bust obviously larger and fuller so the size-up is easy to see. "
                "Keep every breast fully covered by the same shirt — if the bigger chest "
                "would overflow, extend and stretch that same fabric naturally so it still "
                "covers. Show a cleavage line at the existing collar under the cloth. "
                "Do not pop out of the neckline. Do not undress. Do not make her nude or topless."
            )
        )
        self.assertEqual(r.reason, "clothed_body_enhance_pattern")
        self.assertTrue(r.params_hints.get("clothed_enhance"))
        self.assertNotIn("clothes_remover", r.params_hints.get("loras") or [])
        self.assertIn("breast_enhance", r.params_hints.get("loras") or [])

    def test_enhance_ass_preset_targets_ass(self) -> None:
        prompt = (
            "Photorealistic edit of the exact woman in the start image. "
            "CRITICAL: keep her exact same face, hair, pose, framing, lighting, background, "
            "and the SAME clothes fully on — same outfit, fabric, color, and coverage. "
            "Do not undress. Do not make her nude or topless. Do not change her breasts or cleavage. "
            "Only change this: enhance her ass/hips from this camera view — make her ass and "
            "hips clearly larger and rounder while clothed, with fabric stretching naturally "
            "over the bigger shapes. "
            "Crisp focus, realistic cloth folds, no face morphing."
        )
        r = rules.classify(_req(prompt))
        self.assertEqual(r.reason, "clothed_body_enhance_pattern")
        self.assertTrue(r.params_hints.get("clothed_enhance"))
        self.assertEqual(r.targets[0]["label"], "ass")
        self.assertEqual(r.params_hints.get("loras"), ["nsfw_unlock"])

    def test_enhance_both_preset_targets_curves(self) -> None:
        prompt = (
            "Photorealistic edit of the exact woman in the start image. "
            "CRITICAL: keep her exact same face, hair, pose, framing, lighting, background, "
            "and the SAME clothes fully on — same outfit, fabric, color, and coverage. "
            "Do not undress. Do not make her nude or topless. "
            "Only change this: enhance her look from this camera view — make breasts/cleavage "
            "clearly larger and fuller and make her ass/hips clearly larger and rounder while "
            "clothed, with fabric stretching naturally over the bigger shapes. "
            "Crisp focus, realistic cloth folds, no face morphing."
        )
        r = rules.classify(_req(prompt))
        self.assertEqual(r.reason, "clothed_body_enhance_pattern")
        self.assertEqual(r.targets[0]["label"], "curves")
        self.assertNotIn("clothes_remover", r.params_hints.get("loras") or [])
        self.assertIn("breast_enhance", r.params_hints.get("loras") or [])

    def test_undress_still_wins_when_explicit(self) -> None:
        r = rules.classify(_req("make her nude and show her breasts"))
        self.assertEqual(r.reason, "undress_nsfw_pattern")
        self.assertIn("clothes_remover", r.params_hints.get("loras") or [])

    def test_background_replace(self) -> None:
        r = rules.classify(_req("change the background to a beach"))
        self.assertEqual(r.task_type, "edit.background")
        self.assertTrue(r.bypass_vlm)


class AiEnginePhase2VlmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bootstrap_models()
        bootstrap_workflows()

    def test_vlm_unavailable_degrades(self) -> None:
        available = registry.available_task_types(channel="stable")
        with patch.object(vlm, "plan_with_vlm", return_value=None):
            p = plan(_req("fix it"), available_task_types=available)
        self.assertEqual(p.planner_path, "rules")
        self.assertIn("vlm_unavailable_degraded_to_rules", p.warnings)
        self.assertIn(p.task_type, ("image.img2img", "edit.general_instruction"))

    def test_vlm_enrichment_when_mocked(self) -> None:
        available = registry.available_task_types(channel="stable")
        fake = vlm.VlmPlanResult(
            task_type="edit.clothing_replace",
            confidence=0.93,
            targets=[{"label": "shirt", "role": "replace_region"}],
            prompts={
                "user": "fix it",
                "positive": "Change the shirt to blue denim, preserve identity",
                "negative": "blurry",
            },
            perception=["grounding", "sam2"],
            identity={"enabled": True, "method": "pulid"},
            post_hints=["face_detailer"],
            model_id="vlm.qwen25_vl_7b",
        )
        with patch.object(vlm, "plan_with_vlm", return_value=fake):
            p = plan(_req("fix it"), available_task_types=available)
        self.assertEqual(p.planner_path, "vlm")
        self.assertEqual(p.intent_task_type, "edit.clothing_replace")
        self.assertEqual(p.task_type, "edit.clothing_replace")
        self.assertEqual(p.vlm_model_id, "vlm.qwen25_vl_7b")
        self.assertIn("shirt", p.prompts["positive"].lower() + str(p.targets))

    def test_bypass_does_not_call_vlm(self) -> None:
        available = registry.available_task_types(channel="stable")
        with patch.object(vlm, "plan_with_vlm") as mocked:
            p = plan(_req("upscale to 4k"), available_task_types=available)
            mocked.assert_not_called()
        self.assertEqual(p.planner_path, "rules")
        self.assertEqual(p.intent_task_type, "image.upscale")

    def test_slot_not_hardcoded_in_vlm_module(self) -> None:
        # Architectural guard: public constant is the slot name
        self.assertEqual(vlm._PLANNER_SLOT, "planner.default_model")


if __name__ == "__main__":
    unittest.main()

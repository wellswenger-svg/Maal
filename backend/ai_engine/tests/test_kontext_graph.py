"""Unit tests for Flux Kontext API graph builder."""

from __future__ import annotations

import unittest

from backend.workflows_wan import build_i2i_prompt, build_kontext_edit_prompt


class KontextGraphTests(unittest.TestCase):
    def test_kontext_graph_has_reference_latent(self) -> None:
        g = build_kontext_edit_prompt(
            image_name="in.png",
            positive="Change the shirt to red",
            negative=None,
            flux_unet="flux1-dev-kontext_fp8_scaled.safetensors",
            flux_clip_l="clip_l.safetensors",
            flux_t5="t5xxl_fp8_e4m3fn.safetensors",
            flux_vae="ae.safetensors",
            steps=20,
            guidance=2.5,
            seed=42,
        )
        types = {n["class_type"] for n in g.values()}
        self.assertIn("ReferenceLatent", types)
        self.assertIn("FluxKontextImageScale", types)
        self.assertIn("ConditioningZeroOut", types)
        self.assertNotIn("ModelSamplingFlux", types)
        ks = next(n for n in g.values() if n["class_type"] == "KSampler")
        self.assertEqual(ks["inputs"]["denoise"], 1.0)
        self.assertEqual(g["1"]["inputs"]["unet_name"], "flux1-dev-kontext_fp8_scaled.safetensors")

    def test_i2i_denoise_cap_raised_for_degraded(self) -> None:
        g = build_i2i_prompt(
            image_name="in.png",
            positive="shirt red",
            negative=None,
            flux_unet="flux1-dev-fp8.safetensors",
            flux_clip_l="clip_l.safetensors",
            flux_t5="t5xxl_fp8_e4m3fn.safetensors",
            flux_vae="ae.safetensors",
            width=1024,
            height=1024,
            steps=28,
            guidance=3.5,
            seed=1,
            denoise=0.72,
            denoise_cap=0.88,
            wrap_preserve=False,
        )
        ks = next(n for n in g.values() if n["class_type"] == "KSampler")
        self.assertAlmostEqual(ks["inputs"]["denoise"], 0.72)
        enc = next(n for n in g.values() if n["class_type"] == "CLIPTextEncode")
        # first encode is positive — wrap_preserve False keeps raw text
        pos = g["4"]["inputs"]["text"]
        self.assertEqual(pos, "shirt red")

    def test_i2i_wrap_mode_fabric(self) -> None:
        g = build_i2i_prompt(
            image_name="in.png",
            positive="more volume",
            negative=None,
            flux_unet="flux1-dev-fp8.safetensors",
            flux_clip_l="clip_l.safetensors",
            flux_t5="t5xxl_fp8_e4m3fn.safetensors",
            flux_vae="ae.safetensors",
            width=1024,
            height=1024,
            steps=28,
            guidance=3.5,
            seed=1,
            denoise=0.62,
            denoise_cap=0.70,
            wrap_preserve=False,
            wrap_mode="fabric",
        )
        pos = g["4"]["inputs"]["text"]
        self.assertIn("Fabric may drape", pos)
        self.assertIn("more volume", pos)

    def test_i2i_pulid_nodes(self) -> None:
        g = build_i2i_prompt(
            image_name="in.png",
            positive="edit",
            negative=None,
            flux_unet="flux1-dev-fp8.safetensors",
            flux_clip_l="clip_l.safetensors",
            flux_t5="t5xxl_fp8_e4m3fn.safetensors",
            flux_vae="ae.safetensors",
            width=768,
            height=768,
            steps=20,
            guidance=3.5,
            seed=1,
            denoise=0.40,
            pulid_file="pulid_flux_v0.9.1.safetensors",
        )
        types = {n["class_type"] for n in g.values()}
        self.assertIn("ApplyPulidFlux", types)
        self.assertIn("PulidFluxModelLoader", types)
        self.assertEqual(g["11"]["inputs"]["model"], ["73", 0])
        self.assertEqual(g["70"]["inputs"]["pulid_file"], "pulid_flux_v0.9.1.safetensors")

    def test_i2i_pose_controlnet_nodes(self) -> None:
        g = build_i2i_prompt(
            image_name="in.png",
            positive="on all fours",
            negative=None,
            flux_unet="flux1-dev-kontext_fp8_scaled.safetensors",
            flux_clip_l="clip_l.safetensors",
            flux_t5="t5xxl_fp8_e4m3fn.safetensors",
            flux_vae="ae.safetensors",
            width=768,
            height=768,
            steps=28,
            guidance=4.0,
            seed=1,
            denoise=0.88,
            denoise_cap=0.92,
            controlnet_name="flux_shakker_labs_union_pro-fp8_e4m3fn.safetensors",
            control_image_name="pose.png",
            control_type="pose",
            control_strength=0.72,
        )
        types = {n["class_type"] for n in g.values()}
        self.assertIn("ControlNetLoader", types)
        self.assertIn("SetUnionControlNetType", types)
        self.assertIn("ControlNetApplyAdvanced", types)
        self.assertEqual(g["17"]["inputs"]["type"], "pose")
        ks = g["11"]["inputs"]
        self.assertEqual(ks["positive"], ["18", 0])
        self.assertEqual(ks["negative"], ["18", 1])


if __name__ == "__main__":
    unittest.main()

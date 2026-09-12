"""Tests for Wan I2V dual-stage LoRA injection + stack resolve."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.ai_engine.workflows.video_i2v import lora_stack as ls
from backend.workflows_wan import build_i2v_prompt


class DualStageLoraGraphTests(unittest.TestCase):
    def _base_kwargs(self, **extra):
        kw = dict(
            image_name="in.png",
            positive="test motion",
            negative=None,
            unet_high="high.safetensors",
            unet_low="low.safetensors",
            vae="vae.safetensors",
            clip="clip.safetensors",
            width=640,
            height=640,
            length=49,
            steps=32,
            cfg=3.5,
            seed=1,
            fps=16,
            shift=5.0,
        )
        kw.update(extra)
        return kw

    def test_no_loras_uses_raw_unets(self) -> None:
        g = build_i2v_prompt(**self._base_kwargs())
        self.assertEqual(g["8"]["inputs"]["model"], ["1", 0])
        self.assertEqual(g["9"]["inputs"]["model"], ["2", 0])
        self.assertFalse(
            any(n.get("class_type") == "LoraLoaderModelOnly" for n in g.values())
        )

    def test_high_and_low_chains(self) -> None:
        g = build_i2v_prompt(
            **self._base_kwargs(
                loras_high=[("a_high.safetensors", 1.2), ("b_high.safetensors", 0.5)],
                loras_low=[("a_low.safetensors", 1.1)],
            )
        )
        lora_nodes = {
            k: v
            for k, v in g.items()
            if v.get("class_type") == "LoraLoaderModelOnly"
        }
        self.assertEqual(len(lora_nodes), 3)
        # First high LoRA takes UNET 1
        self.assertEqual(g["30"]["inputs"]["model"], ["1", 0])
        self.assertEqual(g["30"]["inputs"]["lora_name"], "a_high.safetensors")
        self.assertEqual(g["30"]["inputs"]["strength_model"], 1.2)
        self.assertEqual(g["31"]["inputs"]["model"], ["30", 0])
        # Low chain starts after high chain ids
        self.assertEqual(g["32"]["inputs"]["model"], ["2", 0])
        self.assertEqual(g["32"]["inputs"]["lora_name"], "a_low.safetensors")
        # ModelSamplingSD3 points at chain tails
        self.assertEqual(g["8"]["inputs"]["model"], ["31", 0])
        self.assertEqual(g["9"]["inputs"]["model"], ["32", 0])
        # Never use LoraLoader (clip) on video path
        self.assertFalse(any(n.get("class_type") == "LoraLoader" for n in g.values()))


class LoraStackResolveTests(unittest.TestCase):
    def _patch_lora_dirs(self, dirs: list[Path]):
        """Patch dirs on the private overlay module (bind copies leave globals there)."""
        import sys

        # Ensure overlay is loaded.
        from backend.ai_engine.workflows.video_i2v import lora_stack as _ls  # noqa: F401

        priv = sys.modules.get("wan_private_lora_stack")
        self.assertIsNotNone(priv)
        return patch.object(priv, "_lora_dirs", return_value=dirs)

    def test_cap_stage(self) -> None:
        items = [("a.safetensors", 3.0, "a"), ("b.safetensors", 3.0, "b")]
        capped = ls._cap_stage(items)
        total = sum(s for _, s, _ in capped)
        self.assertLessEqual(total, ls.STAGE_STRENGTH_CAP + 1e-6)

    def test_resolve_skips_missing_and_detects_lightx2v(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Wan2.2_LightX2V_high_n54vv.safetensors").write_bytes(b"x" * 2000)
            (root / "Wan2.2_LightX2V_low_n54vv.safetensors").write_bytes(b"x" * 2000)
            (root / "PENISLORA_22_i2v_HIGH_e320.safetensors").write_bytes(b"x" * 2000)
            available = {
                "Wan2.2_LightX2V_high_n54vv.safetensors",
                "Wan2.2_LightX2V_low_n54vv.safetensors",
                "PENISLORA_22_i2v_HIGH_e320.safetensors",
            }

            with self._patch_lora_dirs([root]):
                stack = ls.resolve_video_lora_stack(
                    include_optional=True,
                    available_names=available,
                    trust_remote=False,
                )

            self.assertTrue(stack.lightx2v_active)
            # Quality path keeps full steps; distill override is draft-only.
            self.assertIsNone(stack.steps_override)
            self.assertIn("lightx2v_unc_high", stack.applied_ids)
            self.assertIn("penis_lora_high", stack.applied_ids)
            self.assertIn("male_gen_high", stack.missing_ids)
            high_files = [f for f, _ in stack.high]
            self.assertIn("Wan2.2_LightX2V_high_n54vv.safetensors", high_files)
            self.assertLessEqual(sum(s for _, s in stack.high), ls.STAGE_STRENGTH_CAP + 1e-6)

    def test_resolve_from_comfy_catalog_without_disk(self) -> None:
        available = {
            "male_genitalia_enhancer_high.safetensors",
            "male_genitalia_enhancer_low.safetensors",
            "female_genitalia_enhancer_high.safetensors",
            "female_genitalia_enhancer_low.safetensors",
            "PENISLORA_22_i2v_HIGH_e320.safetensors",
            "PENISLORA_22_i2v_LOW_e496.safetensors",
            "Wan2.2_I2V_Blink_Blowjob_HIGH.safetensors",
            "Wan2.2_I2V_Blink_Blowjob_LOW.safetensors",
            "DR34ML4Y_I2V_14B_HIGH_V2.safetensors",
            "DR34ML4Y_I2V_14B_LOW_V2.safetensors",
            "Cumshot_LoRA.safetensors",
            "Wan2.2_LightX2V_high_n54vv.safetensors",
            "Wan2.2_LightX2V_low_n54vv.safetensors",
        }
        with self._patch_lora_dirs([]):
            stack = ls.resolve_video_lora_stack(
                include_optional=True,
                available_names=available,
                nsfw=True,
            )
        self.assertIn("penis_lora_high", stack.applied_ids)
        self.assertIn("male_gen_high", stack.applied_ids)
        # Deepthroat only when oral/deepthroat motion (not generic NSFW).
        self.assertNotIn("deepthroat_high", stack.applied_ids)
        # Distill skipped on NSFW so anatomy LoRAs keep strength budget.
        self.assertNotIn("lightx2v_unc_high", stack.applied_ids)
        self.assertFalse(stack.lightx2v_active)
        self.assertEqual(stack.missing_ids, [])
        self.assertGreaterEqual(len(stack.high), 3)

    def test_trust_remote_when_no_probe(self) -> None:
        with self._patch_lora_dirs([]):
            stack = ls.resolve_video_lora_stack(
                include_optional=False,
                available_names=None,
                trust_remote=True,
                nsfw=True,
            )
        self.assertIn("penis_lora_high", stack.applied_ids)
        self.assertIn("male_gen_high", stack.applied_ids)
        high_files = [f for f, _ in stack.high]
        self.assertIn("PENISLORA_22_i2v_HIGH_e320.safetensors", high_files)

    def test_empty_catalog_still_trusts_core(self) -> None:
        """Tunnel glitch returning [] must not wipe the NSFW LoRA stack."""
        with self._patch_lora_dirs([]):
            stack = ls.resolve_video_lora_stack(
                include_optional=False,
                available_names=set(),
                trust_remote=True,
                nsfw=True,
                motion_kinds=["nsfw_action", "oral"],
            )
        self.assertIn("penis_lora_high", stack.applied_ids)
        self.assertIn("deepthroat_high", stack.applied_ids)
        self.assertIn("dr34ml4y_high", stack.applied_ids)
        self.assertNotIn("male_gen_high", stack.applied_ids)
        self.assertNotIn("female_gen_high", stack.applied_ids)
        self.assertGreaterEqual(len(stack.high), 2)

    def test_oral_skips_female_gen_budget(self) -> None:
        available = {
            "male_genitalia_enhancer_high.safetensors",
            "male_genitalia_enhancer_low.safetensors",
            "female_genitalia_enhancer_high.safetensors",
            "female_genitalia_enhancer_low.safetensors",
            "PENISLORA_22_i2v_HIGH_e320.safetensors",
            "PENISLORA_22_i2v_LOW_e496.safetensors",
            "Wan2.2_I2V_Blink_Blowjob_HIGH.safetensors",
            "Wan2.2_I2V_Blink_Blowjob_LOW.safetensors",
            "DR34ML4Y_I2V_14B_HIGH_V2.safetensors",
            "DR34ML4Y_I2V_14B_LOW_V2.safetensors",
            "Cumshot_LoRA.safetensors",
        }
        with self._patch_lora_dirs([]):
            stack = ls.resolve_video_lora_stack(
                include_optional=True,
                available_names=available,
                nsfw=True,
                motion_kinds=["nsfw_action", "oral"],
            )
        self.assertIn("penis_lora_high", stack.applied_ids)
        self.assertIn("deepthroat_high", stack.applied_ids)
        self.assertIn("dr34ml4y_high", stack.applied_ids)
        self.assertIn("dr34ml4y_low", stack.applied_ids)
        self.assertNotIn("male_gen_high", stack.applied_ids)
        self.assertNotIn("female_gen_high", stack.applied_ids)
        self.assertNotIn("cumshot_high", stack.applied_ids)
        self.assertNotIn("cumshot_low", stack.applied_ids)

    def test_oral_stacks_blink_and_dr34(self) -> None:
        available = {
            "PENISLORA_22_i2v_HIGH_e320.safetensors",
            "Wan2.2_I2V_Blink_Blowjob_HIGH.safetensors",
            "DR34ML4Y_I2V_14B_HIGH_V2.safetensors",
        }
        with self._patch_lora_dirs([]):
            stack = ls.resolve_video_lora_stack(
                include_optional=False,
                available_names=available,
                nsfw=True,
                motion_kinds=["nsfw_action", "oral", "deepthroat"],
            )
        self.assertIn("deepthroat_high", stack.applied_ids)
        self.assertIn("dr34ml4y_high", stack.applied_ids)

    def test_missionary_loads_pose_lora_skips_deepthroat(self) -> None:
        available = {
            "male_genitalia_enhancer_high.safetensors",
            "male_genitalia_enhancer_low.safetensors",
            "female_genitalia_enhancer_high.safetensors",
            "female_genitalia_enhancer_low.safetensors",
            "PENISLORA_22_i2v_HIGH_e320.safetensors",
            "PENISLORA_22_i2v_LOW_e496.safetensors",
            "Wan2.2_I2V_Blink_Blowjob_HIGH.safetensors",
            "Wan2.2_I2V_Blink_Blowjob_LOW.safetensors",
            "DR34ML4Y_I2V_14B_HIGH_V2.safetensors",
            "DR34ML4Y_I2V_14B_LOW_V2.safetensors",
            "Wan2.2_I2V_Missionary_HIGH.safetensors",
            "Wan2.2_I2V_Missionary_LOW.safetensors",
        }
        with self._patch_lora_dirs([]):
            stack = ls.resolve_video_lora_stack(
                include_optional=True,
                available_names=available,
                nsfw=True,
                motion_kinds=["nsfw_action", "penetration", "missionary"],
            )
        self.assertIn("missionary_high", stack.applied_ids)
        self.assertIn("missionary_low", stack.applied_ids)
        self.assertIn("dr34ml4y_high", stack.applied_ids)
        self.assertIn("dr34ml4y_low", stack.applied_ids)
        high_files = [f for f, _ in stack.high]
        self.assertIn("DR34ML4Y_I2V_14B_HIGH_V2.safetensors", high_files)
        self.assertIn("female_gen_high", stack.applied_ids)
        self.assertNotIn("deepthroat_high", stack.applied_ids)
        # Dropped optional pose LoRAs must not reappear.
        self.assertNotIn("cowgirl_high", stack.applied_ids)
        self.assertNotIn("doggy_high", stack.applied_ids)
        self.assertNotIn("handjob_high", stack.applied_ids)

    def test_skips_corrupt_local_safetensors(self) -> None:
        """Truncated enhancer must not be queued (Sex crash: invalid size 95251)."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            # Fake a large truncated file (>1MB) that is not valid safetensors.
            bad = d / "female_genitalia_enhancer_high.safetensors"
            bad.write_bytes(b"not-a-safetensors-file" + b"\0" * (1_000_001))
            good = d / "PENISLORA_22_i2v_HIGH_e320.safetensors"
            good.write_bytes(b"stub")
            available = {
                "female_genitalia_enhancer_high.safetensors",
                "PENISLORA_22_i2v_HIGH_e320.safetensors",
            }
            with self._patch_lora_dirs([d]):
                hit_bad = ls.find_lora_file(
                    ("female_genitalia_enhancer_high.safetensors",),
                    available_names=available,
                    trust_remote=False,
                )
                hit_good = ls.find_lora_file(
                    ("PENISLORA_22_i2v_HIGH_e320.safetensors",),
                    available_names=available,
                    trust_remote=False,
                )
            self.assertIsNone(hit_bad)
            self.assertEqual(hit_good, "PENISLORA_22_i2v_HIGH_e320.safetensors")

    def test_cumshot_loads_high_and_low(self) -> None:
        available = {
            "PENISLORA_22_i2v_HIGH_e320.safetensors",
            "PENISLORA_22_i2v_LOW_e496.safetensors",
            "Wan2.2_I2V_Cumshot_HIGH.safetensors",
            "Cumshot_LoRA.safetensors",
            "male_genitalia_enhancer_high.safetensors",
            "male_genitalia_enhancer_low.safetensors",
        }
        with self._patch_lora_dirs([]):
            stack = ls.resolve_video_lora_stack(
                include_optional=False,
                available_names=available,
                nsfw=True,
                motion_kinds=["nsfw_action", "cumshot"],
            )
        self.assertIn("cumshot_high", stack.applied_ids)
        self.assertIn("cumshot_low", stack.applied_ids)
        high_map = {f: s for f, s in stack.high}
        low_map = {f: s for f, s in stack.low}
        self.assertAlmostEqual(high_map["Wan2.2_I2V_Cumshot_HIGH.safetensors"], 0.70)
        self.assertAlmostEqual(low_map["Cumshot_LoRA.safetensors"], 0.95)

    def test_pose_lora_alias_filename(self) -> None:
        available = {
            "Wan2.2 - I2V - Missionary Sex - HIGH 14B.safetensors",
            "Wan2.2 - I2V - Missionary Sex - LOW 14B.safetensors",
            "PENISLORA_22_i2v_HIGH_e320.safetensors",
        }
        with self._patch_lora_dirs([]):
            stack = ls.resolve_video_lora_stack(
                include_optional=True,
                available_names=available,
                nsfw=True,
                motion_kinds=["nsfw_action", "penetration", "missionary"],
            )
        self.assertIn("missionary_high", stack.applied_ids)
        self.assertIn("missionary_low", stack.applied_ids)
        high_files = [f for f, _ in stack.high]
        self.assertIn(
            "Wan2.2 - I2V - Missionary Sex - HIGH 14B.safetensors",
            high_files,
        )

"""Phase 6 tests: video_i2v.v1 profiles, motion scaffold, registry preference."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from backend.ai_engine.models.catalog import bootstrap_models
from backend.ai_engine.planner import plan
from backend.ai_engine.post.pipeline import run_post
from backend.ai_engine.registry.catalog import bootstrap_workflows
from backend.ai_engine.registry.workflows import registry
from backend.ai_engine.schema import EngineResult, ExecutionPlan, GenerateRequest
from backend.ai_engine.workflows.video_i2v.motion import (
    extract_motion_hints,
    frames_for_seconds,
    profile_video_params,
    scaffold_i2v_prompt,
    snap_wan_length,
)
from backend.ai_engine.workflows.video_i2v import v1 as vid_v1
from backend.config import get_settings


def _req(prompt: str, mode: str = "vid", **kw) -> GenerateRequest:
    return GenerateRequest(
        mode=mode,  # type: ignore[arg-type]
        prompt=prompt,
        prompt_english=prompt,
        image_bytes=b"\x89PNG" + b"\x00" * 32,
        **kw,
    )


class Phase6MotionTests(unittest.TestCase):
    def test_extract_pan_zoom(self) -> None:
        m = extract_motion_hints("slow pan and gentle zoom in")
        self.assertIn("pan", m["motion_kinds"])
        self.assertIn("zoom", m["motion_kinds"])

    def test_extract_subtle_default(self) -> None:
        m = extract_motion_hints("animate this photo")
        self.assertTrue(m["motion_kinds"])
        self.assertEqual(m["amplitude"], "medium")

    def test_scaffold_locks_identity(self) -> None:
        text = scaffold_i2v_prompt(
            "subtle smile",
            {"motion_kinds": ["expression"], "amplitude": "low"},
        )
        self.assertIn("start frame", text.lower())
        self.assertIn("smile", text.lower())
        self.assertIn("subtle", text.lower())

    def test_scaffold_nsfw_oral(self) -> None:
        m = extract_motion_hints("give blowjob to a penis")
        self.assertTrue(m["nsfw"])
        self.assertIn("oral", m["motion_kinds"])
        text = scaffold_i2v_prompt("give blowjob to a penis", m)
        self.assertIn("PENISLORA", text)
        self.assertIn("erect penis", text.lower())
        self.assertIn("a man appears and she sucks his penis", text.lower())
        self.assertIn("exact face", text.lower())
        self.assertIn("man fully in frame", text.lower())
        # Keep NSFW scaffolds short — long dumps mush start-frame identity.
        self.assertLess(len(text), 700)
        self.assertNotIn("follow this sequence", text.lower())
        self.assertNotIn("scene lock", text.lower())

    def test_extract_pose_missionary(self) -> None:
        m = extract_motion_hints("missionary sex thrusting")
        self.assertTrue(m["nsfw"])
        self.assertIn("penetration", m["motion_kinds"])
        self.assertIn("missionary", m["motion_kinds"])
        text = scaffold_i2v_prompt("missionary sex thrusting", m)
        self.assertIn("missionary", text.lower())
        self.assertIn("vagina", text.lower())

    def test_extract_pose_cowgirl_doggy_handjob(self) -> None:
        cg = extract_motion_hints("cowgirl riding")
        self.assertIn("cowgirl", cg["motion_kinds"])
        self.assertIn("penetration", cg["motion_kinds"])
        dg = extract_motion_hints("doggy style from behind")
        self.assertIn("doggy", dg["motion_kinds"])
        hj = extract_motion_hints("handjob stroking the penis")
        self.assertIn("handjob", hj["motion_kinds"])
        self.assertNotIn("oral", hj["motion_kinds"])
        text = scaffold_i2v_prompt("handjob stroking the penis", hj)
        self.assertIn("hand", text.lower())

    def test_extract_bj_alias_and_cumshot(self) -> None:
        m = extract_motion_hints("bj then cumshot facial")
        self.assertIn("oral", m["motion_kinds"])
        self.assertIn("cumshot", m["motion_kinds"])

    def test_profile_table(self) -> None:
        d = profile_video_params("draft")
        q = profile_video_params("quality")
        u = profile_video_params("ultra")
        self.assertLess(d["steps"], q["steps"])
        self.assertEqual(q["post"], [])
        self.assertIn("frame_upscale", u["post"])
        self.assertTrue(d["lightx2v"])
        self.assertEqual(q["fps"], 16)
        self.assertGreaterEqual(q["max_side"], 832)
        self.assertGreaterEqual(q["steps"], 42)

    def test_frames_for_seconds(self) -> None:
        self.assertEqual(frames_for_seconds(2, 16), 33)
        self.assertEqual(frames_for_seconds(3, 16), 49)
        self.assertEqual(frames_for_seconds(4, 16), 65)
        self.assertEqual(frames_for_seconds(5, 16), 81)
        self.assertEqual(snap_wan_length(50), 49)
        self.assertTrue((frames_for_seconds(3, 16) - 1) % 4 == 0)


class Phase6RegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bootstrap_models()
        bootstrap_workflows(force=True)

    def test_v1_preferred_over_legacy(self) -> None:
        wf = registry.resolve("video.i2v", channel="stable")
        self.assertEqual(wf.workflow_ref, "video_i2v.v1")
        legacy = registry.get("video_i2v.v0_legacy")
        self.assertIsNotNone(legacy)
        self.assertTrue(legacy.enabled)
        # v1 must not silent-fallback to LoRA-less legacy (tunnel drops used to do this)
        self.assertIsNone(wf.fallback_workflow_ref)

    def test_planner_motion_hints(self) -> None:
        available = registry.available_task_types(channel="stable")
        p = plan(_req("make a video with a slow camera pan"), available_task_types=available)
        self.assertEqual(p.task_type, "video.i2v")
        motion = (p.params_hints or {}).get("motion") or {}
        self.assertIn("pan", motion.get("motion_kinds") or [])

    def test_quality_profile_skips_rife_for_sharpness(self) -> None:
        wf = registry.get("video_i2v.v1")
        assert wf is not None
        self.assertNotIn("rife_16_to_24", wf.quality_profiles["quality"].post_processing)
        self.assertGreaterEqual(int(wf.quality_profiles["quality"].steps), 42)


class Phase6RunnerPostTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bootstrap_models()
        bootstrap_workflows(force=True)

    async def test_runner_passes_profile_knobs(self) -> None:
        settings = get_settings()
        plan = ExecutionPlan(
            planner_path="rules",
            task_type="video.i2v",
            confidence=0.96,
            profile="draft",
            prompts={"positive": "subtle smile"},
            params_hints={
                "motion": {"motion_kinds": ["expression"], "amplitude": "low"}
            },
        )
        mock_client = AsyncMock()
        mock_client.generate_video = AsyncMock(return_value=(b"FAKEVID" + b"\x00" * 64, "video/mp4"))
        mock_client.list_lora_filenames = AsyncMock(return_value=set())

        with patch(
            "backend.ai_engine.workflows.video_i2v.v1.ComfyClient",
            return_value=mock_client,
        ), patch(
            "backend.ai_engine.workflows.video_i2v.lora_stack._lora_dirs",
            return_value=[],
        ), patch(
            "backend.ai_engine.workflows.video_i2v.lora_stack.find_lora_file",
            return_value=None,
        ):
            data, ctype, kind, label = await vid_v1.run_i2v_v1(
                image_bytes=b"\x89PNG" + b"\x00" * 32,
                prompt="subtle smile",
                negative=None,
                seed=1,
                settings=settings,
                plan=plan,
                profile="draft",
            )
        self.assertEqual(kind, "vid")
        self.assertEqual(ctype, "video/mp4")
        self.assertGreater(len(data), 32)
        kwargs = mock_client.generate_video.await_args.kwargs
        self.assertEqual(kwargs["steps"], 12)
        self.assertEqual(kwargs["length"], 33)
        self.assertEqual(kwargs["fps"], 12)
        self.assertEqual(kwargs["width"], 480)
        # Prompt scaffolded
        args = mock_client.generate_video.await_args.args
        self.assertIn("start frame", args[1].lower())
        self.assertIn("lightx2v", label)
    async def test_post_rife_annotates_target_fps(self) -> None:
        wf = registry.get("video_i2v.v1")
        assert wf is not None
        plan = ExecutionPlan(
            planner_path="rules",
            task_type="video.i2v",
            confidence=0.9,
            profile="quality",
            params_hints={"gen_fps": 16},
            post_hints=["rife_16_to_24"],
        )
        result = EngineResult(
            data=b"FAKEVID" + b"\x00" * 64,
            content_type="video/mp4",
            kind="vid",
            model_label="test",
            workflow_ref=wf.workflow_ref,
            plan=plan,
        )
        out = await run_post(result, wf, plan)
        self.assertEqual(plan.params_hints.get("interp_target_fps"), 24)
        self.assertTrue(
            any("interp_deferred" in w or "rife" in w for w in out.warnings)
        )


if __name__ == "__main__":
    unittest.main()

"""Shared Flux edit runner. Prompt overlays load from gitignored private/."""

from __future__ import annotations

from typing import Any, Optional

from backend.ai_engine.runtime_overlay import bind_module


def build_edit_prompt(user_prompt: str, **kwargs: Any) -> str:
    return (user_prompt or "").strip()


def pad_for_outpaint(image_bytes: bytes, pad_ratio: float = 0.15) -> bytes:
    return image_bytes


def simple_upscale(image_bytes: bytes, scale: float = 2.0) -> bytes:
    return image_bytes


async def run_flux_edit(**kwargs: Any) -> tuple[bytes, str, str, str]:
    from backend.ai_engine.runtime_overlay import load_private_module

    mod = load_private_module("edit_runner")
    fn = getattr(mod, "run_flux_edit", None) if mod is not None else None
    if fn is None:
        raise RuntimeError("Private runtime overlay not installed")
    return await fn(**kwargs)


def make_runner(
    task_kind: str,
    *,
    preprocess: Optional[str] = None,
    denoise_override: Optional[float] = None,
):
    async def _runner(**kwargs: Any) -> tuple[bytes, str, str, str]:
        from backend.ai_engine.runtime_overlay import load_private_module

        mod = load_private_module("edit_runner")
        fn = getattr(mod, "run_flux_edit", None) if mod is not None else None
        if fn is None:
            raise RuntimeError("Private runtime overlay not installed")
        return await fn(
            task_kind=task_kind,
            preprocess=preprocess,
            denoise_override=denoise_override,
            **kwargs,
        )

    return _runner


bind_module("edit_runner", globals())

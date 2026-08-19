"""
Wan Studio — true img2img latent for Wan 2.2 TI2V + remote scrub HTTP routes.

Wan22ImageToVideoLatent keeps start-frame latents in RAW VAE space (noise_mask=0).
Removing that mask and sampling causes garbled RGB (wrong latent scale).

This node encodes the start image, applies Wan22 process_out to the full latent,
and omits noise_mask so KSampler can do real denoise-based edits (outfit, etc.).

Also registers POST /wan_studio/scrub so the Render API can wipe input/output/temp
on this GPU box (local Path wipe does not work across the Cloudflare tunnel).
"""

from __future__ import annotations

import os
from pathlib import Path

import torch

import comfy.model_management
import comfy.utils
import comfy.latent_formats
import nodes

# Filenames produced by Wan Studio workflows (see backend/workflows_wan.py + scrub.py)
_OUR_PREFIXES = (
    "wan_in_",
    "wan_i2i",
    "wan_i2v",
    "wan_i2v14",
    "flux_i2i",
    "flux_kontext",
    "ComfyUI_temp",
)


class Wan22ImageToImageLatent:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "vae": ("VAE",),
                "start_image": ("IMAGE",),
                "width": (
                    "INT",
                    {
                        "default": 1024,
                        "min": 32,
                        "max": nodes.MAX_RESOLUTION,
                        "step": 32,
                    },
                ),
                "height": (
                    "INT",
                    {
                        "default": 1024,
                        "min": 32,
                        "max": nodes.MAX_RESOLUTION,
                        "step": 32,
                    },
                ),
                "batch_size": ("INT", {"default": 1, "min": 1, "max": 4096}),
            }
        }

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "create"
    CATEGORY = "model/conditioning/wan"

    def create(self, vae, start_image, width, height, batch_size=1):
        device = comfy.model_management.intermediate_device()
        # Single still → one temporal slot for TI2V-5B
        latent = torch.zeros(
            [1, 48, 1, height // 16, width // 16],
            device=device,
        )

        start_image = comfy.utils.common_upscale(
            start_image[:1].movedim(-1, 1), width, height, "bilinear", "center"
        ).movedim(1, -1)
        encoded = vae.encode(start_image)
        t = min(encoded.shape[-3], latent.shape[-3])
        latent[:, :, :t] = encoded[:, :, :t]

        # Full process_out so KSampler sees the correct Wan22 scale (true img2img)
        latent_format = comfy.latent_formats.Wan22()
        latent = latent_format.process_out(latent)

        return (
            {
                "samples": latent.repeat((batch_size,) + (1,) * (latent.ndim - 1)),
            },
        )


NODE_CLASS_MAPPINGS = {
    "Wan22ImageToImageLatent": Wan22ImageToImageLatent,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Wan22ImageToImageLatent": "Wan22 Image to Image Latent",
}


def _folder_base(folder_type: str):
    import folder_paths

    return folder_paths.get_directory_by_type(folder_type)


def _resolve_safe(folder_type: str, subfolder: str, filename: str) -> Path | None:
    """Resolve a path under input/output/temp only (blocks traversal)."""
    if folder_type not in ("input", "output", "temp"):
        return None
    if not filename or Path(filename).name != filename:
        return None
    if ".." in filename or "/" in filename or "\\" in filename:
        return None
    base = _folder_base(folder_type)
    if not base:
        return None
    base_abs = os.path.abspath(base)
    target = os.path.abspath(os.path.join(base_abs, subfolder or "", filename))
    try:
        if os.path.commonpath([base_abs, target]) != base_abs:
            return None
    except ValueError:
        return None
    return Path(target)


def _unlink(path: Path) -> bool:
    try:
        if path.is_file():
            path.unlink(missing_ok=True)
            return True
    except OSError:
        pass
    return False


def _wipe_prefixes() -> list[str]:
    wiped: list[str] = []
    for folder_type in ("input", "output", "temp"):
        base = _folder_base(folder_type)
        if not base or not os.path.isdir(base):
            continue
        root = Path(base)
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            name = path.name
            if name.startswith(_OUR_PREFIXES) or name.startswith("wan_"):
                if _unlink(path):
                    wiped.append(str(path))
    return wiped


def _register_scrub_routes() -> None:
    try:
        from aiohttp import web
        from server import PromptServer
    except Exception as exc:
        print(f"[wan_studio_i2i] scrub routes not registered: {exc}")
        return

    routes = PromptServer.instance.routes

    @routes.post("/wan_studio/scrub")
    async def wan_studio_scrub(request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}

        wiped: list[str] = []
        for item in data.get("files") or []:
            if not isinstance(item, dict):
                continue
            path = _resolve_safe(
                str(item.get("type") or "output"),
                str(item.get("subfolder") or ""),
                str(item.get("filename") or ""),
            )
            if path and _unlink(path):
                wiped.append(str(path))

        if data.get("wipe_prefixes", True):
            wiped.extend(_wipe_prefixes())

        # de-dupe
        wiped = list(dict.fromkeys(wiped))
        return web.json_response({"ok": True, "wiped": len(wiped), "paths": wiped})

    @routes.get("/wan_studio/scrub_ping")
    async def wan_studio_scrub_ping(_request):
        return web.json_response({"ok": True, "service": "wan_studio_scrub"})

    print("[wan_studio_i2i] registered POST /wan_studio/scrub")


_register_scrub_routes()

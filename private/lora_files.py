"""Optional Flux LoRA filenames. Loaded from gitignored private/lora_files.py.

On-disk names stay generic (non-graphic). Civitai/HF source pins live in catalog_loras.py.

Image acts (BJ/HJ/titjob) and wet/sheer shirt paths were removed — use Wan I2V for acts.
"""

LORA_FILES = {
    "clothes_remover": "clothes_remover_v0.safetensors",
    "content_unlock": "aidmaNSFWunlock-FLUX-V0.2.safetensors",
    # Flux.1 D Non-Face Altering v2 (Civitai 858262) — Dev img2img + face mask.
    # A/B alt: COF_v6_rollback.safetensors. Kontext Cumifier parked as flux_kontext_fluid_v1.
    "cof": "flux_facial_fluid_v1.safetensors",
    "bust_enhance": "flux_kontext_figure_reshape_v1.safetensors",
    "nsfw_unlock": "aidmaNSFWunlock-FLUX-V0.2.safetensors",
    "breast_enhance": "flux_kontext_figure_reshape_v1.safetensors",
    # Same Kontext reshape as bust (breasts + butts trained together).
    "ass_enhance": "flux_kontext_figure_reshape_v1.safetensors",
    "hip_enhance": "flux_kontext_figure_reshape_v1.safetensors",
}

LORA_DEFAULT_STRENGTH = {
    "clothes_remover": 0.85,
    "content_unlock": 0.80,
    "nsfw_unlock": 0.80,
    # Stronger gel on Dev img2img; identity via face mask + highlight composite.
    "cof": 0.88,
    # Clothed reshape (Flux Kontext). Civitai 1802814 → flux_kontext_figure_reshape_v1.
    "bust_enhance": 0.82,
    "breast_enhance": 0.82,
    "ass_enhance": 0.82,
    "hip_enhance": 0.82,
}

WAN_NEGATIVE_EXTRA = (
    "censored, mosaic, collapsed anatomy, missing partner, "
    "floating anatomy, disembodied body part, missing torso"
)

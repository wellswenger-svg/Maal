"""Optional Flux LoRA filenames. Loaded from gitignored private/lora_files.py.

On-disk names stay generic (non-graphic). Civitai source pins live in catalog_loras.py.
"""

LORA_FILES = {
    "clothes_remover": "clothes_remover_v0.safetensors",
    "content_unlock": "aidmaNSFWunlock-FLUX-V0.2.safetensors",
    "cof": "COF_v6.safetensors",
    "see_through": "See_through_clothes_FLUX.safetensors",
    "wet_shirt": "WetshirtForFlux-1.4.safetensors",
    "bust_enhance": "flux_kontext_figure_reshape_v1.safetensors",
    "nsfw_unlock": "aidmaNSFWunlock-FLUX-V0.2.safetensors",
    "breast_enhance": "flux_kontext_figure_reshape_v1.safetensors",
    "ass_enhance": "flux_clothed_figure_hip_v1.safetensors",
    "hip_enhance": "flux_clothed_figure_hip_v1.safetensors",
}

LORA_DEFAULT_STRENGTH = {
    "clothes_remover": 0.85,
    "content_unlock": 0.80,
    "nsfw_unlock": 0.80,
    "cof": 0.90,
    "see_through": 0.90,
    "wet_shirt": 0.88,
    # Front clothed reshape (Flux Kontext). Civitai 1802814 → flux_kontext_figure_reshape_v1.
    "bust_enhance": 0.65,
    "breast_enhance": 0.65,
    "ass_enhance": 0.72,
    "hip_enhance": 0.72,
}

WAN_NEGATIVE_EXTRA = (
    "censored, mosaic, collapsed anatomy, missing partner, "
    "floating anatomy, disembodied body part, missing torso"
)

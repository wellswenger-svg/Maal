"""Optional Flux LoRA filenames. Loaded from gitignored private/lora_files.py.

On-disk names stay generic (non-graphic). Civitai/HF source pins live in catalog_loras.py.
"""

LORA_FILES = {
    "clothes_remover": "clothes_remover_v0.safetensors",
    "content_unlock": "aidmaNSFWunlock-FLUX-V0.2.safetensors",
    "cof": "COF_v6.safetensors",
    "see_through": "See_through_clothes_FLUX.safetensors",
    # Invisidude Wet T-Shirt Flux v1.4 (replaces Lurulf Wet_ClothesHair)
    "wet_shirt": "WetshirtForFlux-1.4.safetensors",
    "bust_enhance": "flux_kontext_figure_reshape_v1.safetensors",
    "nsfw_unlock": "aidmaNSFWunlock-FLUX-V0.2.safetensors",
    "breast_enhance": "flux_kontext_figure_reshape_v1.safetensors",
    # Same Kontext reshape as bust (breasts + butts trained together).
    "ass_enhance": "flux_kontext_figure_reshape_v1.safetensors",
    "hip_enhance": "flux_kontext_figure_reshape_v1.safetensors",
    # Img act LoRAs (Flux.1 D) — generic on-disk names; triggers live in edit_runner.
    # Keltezaa Blowjob PoV (replaces getphat bl0j0 / flux_pov_a_v1)
    "oral_pov": "flux_pov_bj_v2.safetensors",
    "male_anatomy": "flux_anatomy_m_v1.safetensors",
    "detailed_hands": "flux_hands_detail_v1.safetensors",
}

LORA_DEFAULT_STRENGTH = {
    "clothes_remover": 0.85,
    "content_unlock": 0.80,
    "nsfw_unlock": 0.80,
    "cof": 0.90,
    "see_through": 0.70,
    "wet_shirt": 0.90,
    # Clothed reshape (Flux Kontext). Civitai 1802814 → flux_kontext_figure_reshape_v1.
    "bust_enhance": 0.82,
    "breast_enhance": 0.82,
    "ass_enhance": 0.82,
    "hip_enhance": 0.82,
    "oral_pov": 0.95,
    "male_anatomy": 0.80,
    "detailed_hands": 0.70,
}

WAN_NEGATIVE_EXTRA = (
    "censored, mosaic, collapsed anatomy, missing partner, "
    "floating anatomy, disembodied body part, missing torso"
)

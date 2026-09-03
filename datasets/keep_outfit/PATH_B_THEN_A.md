# Keep-outfit — current path (2026-09-03)

## Immediate: swap reshape LoRA (Kontext)

Public `Huge_natural_breasts_for_FLUX_v2` failed keep-outfit gates (nipples / junk / no volume under cloth).

**Use instead (replace, do not stack):**

| | |
|--|--|
| Model | [Bigger breasts and butts (Flux Kontext LoRA)](https://civitai.com/models/1802814/bigger-breasts-and-butts-flux-kontext-lora) |
| File | `flux_clothed_figure_volume_v1.safetensors` (latest Kontext version) |
| Comfy path | `models/loras/flux_clothed_figure_volume_v1.safetensors` |
| Wire | `breast_enhance` / `bust_enhance` in `private/lora_files.py` |
| Strength | **0.55–0.70** (start ~0.65) |
| Skip for now | Breast size slider, BustyWomen, Bolt-Ons, Huge Breasts, Skinny&Big — do **not** stack |

### On the GPU PC

1. Download the `.safetensors` from Civitai into Comfy `models/loras/`
2. `git pull` this repo; ensure `private/lora_files.py` + `catalog_loras.py` map to the new file (gitignored — copy overlay / secrets if needed)
3. `python scripts/sync_runtime_overlay.py` if Render uses secrets overlay
4. Gate 3–5 starts + holdout `h03` before calling it done

## Later: custom LoRA (still the real fix)

If Kontext swap is still weak vs refs → semi-gold yes/no → train `keep_outfit_reshape_vN` → replace `breast_enhance` again.  
See `KEEP_OUTFIT_LORA_TRAIN.md`.

Semi-gold GPU candidates (review only): `tmp_test/keep_outfit/semi_gold/` (gitignored).

## Do not

- Stack multiple public bust LoRAs
- More Phase0 denoise loops on `Huge_natural_breasts`
- Train on rejected Phase0/v2 outs
- Put ref-gallery images in gold targets

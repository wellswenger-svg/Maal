# Keep-outfit LoRA training guide

How to get **one** reshape setting that works across many start photos — not a denoise that only fits one image.

## Why 0.84 / 0.82 on one photo is not training

Per-job knobs (denoise, LoRA strength) are **inference settings**. They are tuned to that photo’s lighting, crop, and fabric. They do **not** become the default for everyone.

| Approach | Generalizes? | Use for |
|----------|--------------|---------|
| Per-image denoise (e.g. 0.84) | No | Debug one hard case |
| Freeze defaults on 3–5 fixtures | Yes (product) | Ship keep-outfit |
| Train a Flux LoRA on many pairs | Yes (style/volume) | When frozen defaults still fail across bodies/clothes |

This repo has **no built-in trainer**. Training is done offline (Kohya / OneTrainer / similar), then the `.safetensors` is dropped into Comfy and wired in the overlay.

## What you already have

- Reshape weight in use today: Flux LoRA mapped as `breast_enhance` → `Huge_natural_breasts_for_FLUX_v2.safetensors`
- Keep-outfit path: `keep_outfit_reshape.v1` (img2img + mask + PuLID pass A + soft garment restore)
- Overlay strengths live in gitignored `private/edit_runner.py` / `private/lora_files.py`

Training a **custom** LoRA means replacing or stacking that reshape weight — not re-tuning denoise per upload.

## Goal of a proper keep-outfit LoRA

Teach Flux: **same person, same garment type/color, only change volume under cloth** (photoreal fabric drape).

Do **not** teach: become another person’s body/outfit from the 12-ref gallery.

---

## Phase 0 — Freeze inference first (required)

Before any training, lock defaults on a small fixture set.

1. Pick **3–5** start photos that differ in pose, lighting, shirt color, and framing.
2. Run the same keep-outfit action (e.g. Boobs / Enhance) with **one** denoise and **one** LoRA strength.
3. Score only:
   - Same face / hair / background  
   - Same garment type and color  
   - Visible but photoreal volume change  
   - No rectangle, two-tone overlay, or warped sleeves  
4. Prefer the plan band: denoise **0.55–0.70**, reshape LoRA **~0.65–0.75**.
5. If **≥4/5** pass, freeze those numbers in `private/` and sync with `python scripts/sync_runtime_overlay.py`.

Only train a LoRA if frozen defaults still fail across many real phone photos.

---

## Phase 1 — Build a training dataset

### Pair format

Each example is a **before → after** pair:

| File | Role |
|------|------|
| `###_start.png` | Original user photo (input) |
| `###_target.png` | Edit you already judged “good” (output) |
| Caption / trigger | Short text (see below) |

Sources for `target`: successful keep-outfit runs you liked (local `tmp_test/`, library outputs). Prefer targets that keep identity and clothes; discard smear / neckline / identity drift.

### Size and diversity

| Count | Expectation |
|-------|-------------|
| &lt; 10 pairs | Will overfit like per-image denoise — avoid |
| **20–50 pairs** | Minimum useful |
| 50–100+ | Better generalization |

Vary:

- Skin tone, age appearance, hair  
- Shirt / top colors and necklines  
- Indoor / outdoor lighting  
- Portrait vs mid crop  
- Mild pose differences  

Avoid filling the set with near-duplicates of one person in one outfit.

### Captions (keep them boring)

Use the **same** short pattern for every pair so the LoRA learns the edit, not a novel:

```text
photo of a woman, keep same clothes, volume under cloth, fabric may drape, photoreal
```

Optional rare trigger token (e.g. `korfit`) only if you want an explicit on-switch:

```text
korfit, photo of a woman, keep same clothes, volume under cloth, photoreal
```

Do **not** caption with “make her look like [ref person]” or long graphic lists. Refs are QA for fabric realism only, not training targets.

### What not to put in the set

- The 12-ref gallery as targets (different identities / garments)  
- Nude / undress / outfit-swap outputs  
- Heavy face-morph or melted-fabric fails  
- Upscaled junk with compression artifacts as the only target  

---

## Phase 2 — Train (offline)

Use a Flux-capable LoRA trainer on the **GPU PC** (16GB: prefer fp8 / low-rank / small batch).

### Suggested starting recipe (Flux Dev LoRA)

Adjust names to your trainer UI; values are a sane first pass:

| Setting | Start here |
|---------|------------|
| Base | Flux Dev (same family as Comfy edit backbone) |
| Rank (dim) | 16–32 |
| Alpha | ≈ rank (or rank/2) |
| Learning rate | ~1e-4 (UNet) / lower if unstable |
| Steps / epochs | Enough for ~1–2k steps on 20–50 pairs; stop before identity collapse |
| Resolution | 768–1024, match typical edit size |
| Batch | 1 (16GB) |
| Regularization | Optional: a few unchanged “same clothes, no reshape” pairs at low weight |

Train **img2img-style** if the tool supports start→target conditioning; otherwise captioned target-only is OK but weaker for “edit this photo.”

### Overfitting checks while training

Every N steps, run the **same 3 fixture starts** through Comfy with the WIP LoRA:

- Face still matches start  
- Shirt color/cut still match  
- Volume change present but fabric looks real  

If face or outfit drifts, stop — lower LR / rank / steps, or add more diverse pairs.

### Output

Save something like:

```text
E:\Comfy-Desktop\ComfyUI-Shared\models\loras\keep_outfit_reshape_v1.safetensors
```

---

## Phase 3 — Wire into this project

1. Confirm the file is visible to Comfy (refresh / restart if needed).
2. In gitignored overlay `private/lora_files.py`, map the logical id (keep the id stable):

```text
breast_enhance → keep_outfit_reshape_v1.safetensors
```

   Or add a new id and list it in planner `params_hints.loras` for clothed enhance only.

3. In `private/edit_runner.py`, set strength in the **0.6–0.85** band (start ~0.70). Do not jump back to 1.0+.
4. Upload overlay: `python scripts/sync_runtime_overlay.py`
5. Re-run the **same fixture set** used in Phase 0. Freeze strength only when fixtures still pass.

Tracked git code should stay free of graphic filenames in comments; keep filenames in `private/` only.

---

## Phase 4 — Product defaults after training

Ship one stack:

1. Pass A — identity (PuLID, low denoise)  
2. Pass B — masked reshape + **your** LoRA at frozen strength  
3. Pass C — soft face / strap restore + garment mask  

Denoise stays in **0.55–0.70**. Do not reintroduce per-user 0.84 as a global.

If one body type still fails, add **more pairs of that type** and train **v2** — do not special-case denoise in production for one upload.

---

## Decision tree

```text
One photo looks bad at frozen defaults?
  → Debug garment mask / soft restore / that photo only (not a new global denoise)

Many photos look bad the same way (weak volume / fabric melt)?
  → Improve dataset + train LoRA v2

Many photos fail differently (seams, wrong shirt region)?
  → Fix mask / post (CLIPSeg / SAM / feather) — training will not fix a bad mask
```

---

## Checklist

- [ ] 3–5 fixtures frozen with one denoise + one strength  
- [ ] 20+ diverse start→good-target pairs  
- [ ] Captions are short and consistent (keep clothes / volume under cloth)  
- [ ] No ref-identity targets in the set  
- [ ] Flux LoRA trained and saved under Comfy `models/loras/`  
- [ ] Overlay `lora_files` + strength updated; `sync_runtime_overlay.py` run  
- [ ] Fixtures re-scored; strength frozen  

## Related

- Handoff / eval: [`KEEP_OUTFIT_CONTINUE.md`](KEEP_OUTFIT_CONTINUE.md)  
- Production URLs: [`PRODUCTION_URLS.md`](PRODUCTION_URLS.md)  
- Models catalog notes: [`MODELS.md`](MODELS.md)

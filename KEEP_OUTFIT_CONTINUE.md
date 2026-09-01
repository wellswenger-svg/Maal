# Keep-outfit reshape — continue on next PC

Last machine: Windows (`d:\YtAuto\contrnt`), 2026-09-01.

Do **not** edit `.cursor/plans/keep-outfit_edit_quality_6312ed4d.plan.md`.

Longer train protocol: [`KEEP_OUTFIT_LORA_TRAIN.md`](KEEP_OUTFIT_LORA_TRAIN.md).  
Lab folder notes: [`datasets/keep_outfit/README.md`](datasets/keep_outfit/README.md).

---

## Verdict (why things look like a workaround)

Public busty LoRAs (today: `Huge_natural_breasts_for_FLUX_v2` via overlay id `breast_enhance`) only teach **bigger volume**. They do **not** lock the same garment.

So the product path compensates with:

1. Masked Flux img2img (`keep_outfit_reshape.v1`)
2. PuLID identity pass
3. Fabric prompt wrap + soft garment restore
4. Pass C paste of original face/straps from the **start** photo

Paste-from-ref-gallery / rectangle torso patches are **wrong** and must not be training targets.

**Proper fix:** train a custom Flux LoRA whose only job is *same person, same clothes, volume under cloth*. Until that weight exists, improve mask/restore — do not chase per-photo denoise as “the model.”

---

## LoRA strategy (Civitai vs PixAI — decide once)

Front preset = `enhance_boobs` → `edit.keep_outfit_reshape` + `breast_enhance`.  
Back preset = `enhance_ass` → same task + `ass_enhance`.

| Option | Do it? | Why |
|--------|--------|-----|
| **Integrate PixAI** | **No** | Hosted gen API, not a Comfy LoRA. Breaks PuLID, garment masks, keep-outfit graph, identity lock. |
| **Stack more Civitai bust LoRAs** | **No** | Competing concepts (volume vs cloth vs unlock) → worse drift. |
| **Swap another Civitai bust LoRA into `breast_enhance`** | **Weak short-term only** | Still trained for “bigger,” not “same shirt + natural drape.” Slight bias change, same cloth fight. |
| **Replace with your own keep-outfit LoRA** | **Yes — real fix** | Train on gold pairs → map `breast_enhance` (and later hips) to that `.safetensors`. |
| **Civitai / HuggingFace as download source** | **Yes** | Already how `private/catalog_loras.py` pins URLs. Download files into Comfy `models/loras/` — do **not** call Civitai at runtime. |

**Rule:** Civitai/HF = where weights come from. PixAI = wrong tool for this product path.  
**Wire change:** **replace** the reshape weight for keep-outfit when a custom LoRA exists — do **not** integrate a second public bust LoRA on top.

### Near term (no training yet)

Tune pipeline, not the LoRA catalog:

- Keep denoise **0.62–0.68** (cap band **0.55–0.70**)
- Bust mask / garment intersect — if output ≈ start, restore is too aggressive or mask too small
- Soften post-restore only after local Comfy holdout shows a real Pass B change
- Prefer local Comfy eval before phone → Render

### Medium term (ship quality)

1. Fill `datasets/keep_outfit/gold/` (20+ pairs)
2. Train Flux LoRA per [`KEEP_OUTFIT_LORA_TRAIN.md`](KEEP_OUTFIT_LORA_TRAIN.md)
3. Wire `breast_enhance` → `keep_outfit_reshape_v1.safetensors` in `private/lora_files.py`
4. Holdout `h01` / `h02` → then `python scripts/sync_runtime_overlay.py`

---

## Model wiring already set on this GPU PC (2026-09-01)

Tracked repo has the workflow + planner fallback. **Product LoRA filenames live only in gitignored `private/`.**  
After `git pull` on another PC you still need a copy of `private/` (USB / sync) — GitHub will not have it.

| Logical id | Filename on Comfy shared `models/loras/` | Role | Strength (overlay) |
|------------|------------------------------------------|------|--------------------|
| `breast_enhance` / `bust_enhance` | `Huge_natural_breasts_for_FLUX_v2.safetensors` | Front volume (interim) | **0.72** in edit path |
| `ass_enhance` / `hip_enhance` | `FLUX_FD-LargeButt-SkinnyWaist-FP8.safetensors` | Back / hips volume | **0.70** |
| `nsfw_unlock` | `aidmaNSFWunlock-FLUX-V0.2.safetensors` | Unlock soft-refusal | ~0.95 clothed |
| PuLID | `pulid_flux_v0.9.1.safetensors` (under `models/pulid/`) | Pass A identity | weight ~0.80–0.85 |

Catalog pins (download sources) in `private/catalog_loras.py`:

- Front: Civitai model `780114` → Huge Natural Breasts Flux v2  
- Back: HuggingFace `75dhsx/Felldude` → LargeButt / SkinnyWaist FP8  
- Unlock / wet / COF: see same file  

Overlay files that must exist for keep-outfit to run:

```text
private/planner_rules.py   → clothed_body_enhance_pattern → edit.keep_outfit_reshape
private/edit_runner.py     → Pass A PuLID + Pass B mask + LoRA stack + region lock
private/lora_files.py      → logical id → filename + default strengths
private/presets.json       → enhance_boobs / enhance_ass / enhance
private/catalog_loras.py   → optional Model Manager download pins
```

Verify on the other PC after copy:

```text
python -c "from backend.ai_engine.runtime_overlay import overlay_status; print(overlay_status())"
# expect edit_runner / planner_rules / presets all True

python -c "from backend.ai_engine.models.catalog import _find_weight
for f in ['Huge_natural_breasts_for_FLUX_v2.safetensors','FLUX_FD-LargeButt-SkinnyWaist-FP8.safetensors','aidmaNSFWunlock-FLUX-V0.2.safetensors','pulid_flux_v0.9.1.safetensors']:
 print(f, '->', _find_weight(f))"
```

Comfy on this PC: `COMFYUI_DIR=E:\Comfy-Desktop\ComfyUI-Installs\Khelukhiladi\ComfyUI` with shared models under `E:\Comfy-Desktop\ComfyUI-Shared\models\`. Point the other PC’s `.env` `COMFYUI_URL` at this box’s tunnel / LAN if using remote resources.

---

## What to copy to the next PC

Git does **not** carry media or the overlay. Copy these manually (USB / sync):

| Item | Path on this PC | Required? |
|------|-----------------|-----------|
| Repo | `git pull` `main` on `wellswenger-svg/Maal` | Yes |
| Overlay | `private/` (especially `planner_rules.py`, `edit_runner.py`, `lora_files.py`, `presets.json`, `catalog_loras.py`) | **Yes** — keep-outfit product path |
| Train lab | **entire** `datasets/keep_outfit/` (PNGs are gitignored) | Yes if continuing train lab |
| Secrets | `tokens&cmd`, `.env` / `.env.local` | Yes for deploy/API |
| Optional eval | `tmp_test/first_preset_run/input_*.png` (also already in holdout) | Optional |

After overlay edits on the GPU PC that serves Comfy → Render:  
`python scripts/sync_runtime_overlay.py`

---

## Exact folders to use

```text
datasets/keep_outfit/
  gold/          ← train here (start + target + caption)   [EMPTY now]
  hard/          ← harder same-format pairs                [EMPTY]
  holdout/       ← starts ONLY — never train on these
    h01_start.png   (black tank + open white shirt)
    h02_start.png   (blue ribbed crop)
  reg/           ← start≈target, “no reshape” captions
  scores/
    scorecard.csv
  checkpoints/   ← WIP LoRA .safetensors
  staging/
    starts/      ← waiting for a good clothed target
      s01_black_tank.png
      s02_blue_crop.png
    rejected_notes/
      AUDIT.md   ← why local outs were not gold
```

Check counts anytime:

```text
python scripts/keep_outfit_dataset_lint.py
```

Expect until you fill data: `gold 0`, `holdout 2`, lint exit code 2 (not ready to train).

---

## What NOT to use as gold/hard targets

Do **not** copy these into `gold/` or `hard/` as `*_target.png`:

| Source | Why reject |
|--------|------------|
| `tmp_test/first_preset_run/out_1.png`, `out_2.png` | Nude / identity drift |
| `tmp_test/maxref_run/ref_*.png` | Other identities / outfits (gallery) |
| `tmp_test/maxref_run/out_r2_*` … `out_r4_*` | Visible rectangular paste / wrong garment |
| `tmp_test/maxref_run/out_1.png`, `out_2.png` | Clothes mostly kept but volume too weak/unclear — re-run, don’t train on yet |

Reject any future target that shows: nude/undress, rectangle torso paste, two-tone smear, wrong shirt color/cut, melted neckline, swapped face.

---

## How to fill gold (exact steps)

Goal before training: **20–50 gold pairs**, ~20–30% as many in `hard/`, **5+ holdout starts** (you already have 2).

### A. Get a keeper output

1. Prefer **local Comfy** on the GPU PC (not Render) for Pass A+B speed.
2. Preset / action: clothed enhance mapped to `edit.keep_outfit_reshape` (last eval preset id: `enhance_boobs`).
3. Use starts that are **not** already in `holdout/` for gold training pairs. Holdout starts (`h01`, `h02`) are for **scoring only** after a LoRA exists.
4. Frozen inference band (until fixtures pass):
   - Reshape denoise **0.55–0.70** (planner hint was **0.62**)
   - Reshape LoRA strength **~0.65–0.75** (overlay was **0.72**)
   - Wrap mode **`fabric`**
5. Score a pass only if **all** true:
   - Same face / hair / background as start
   - Same garment **type and color**
   - Visible but photoreal volume under cloth
   - No rectangle, two-tone overlay, paste patch, or nude swap

### B. Save the pair

For the next free id (start at `001`):

```text
datasets/keep_outfit/gold/001_start.png    ← original photo
datasets/keep_outfit/gold/001_target.png   ← keeper output
datasets/keep_outfit/gold/001.txt          ← caption (below)
```

Hard cases (dark shirt, straps, hands in frame, side light) → same naming under `hard/`.

### C. Caption (copy exactly)

Every gold/hard `###.txt`:

```text
photo of a woman, keep same clothes, volume under cloth, fabric may drape, photoreal
```

If you adopt the optional trigger, use it on **every** gold/hard caption:

```text
korfit, photo of a woman, keep same clothes, volume under cloth, photoreal
```

Reg pairs (`reg/`):

```text
photo of a woman, same clothes, no reshape, photoreal
```

Templates also live at:

- `datasets/keep_outfit/gold/_CAPTION_TEMPLATE.txt`
- `datasets/keep_outfit/reg/_CAPTION_TEMPLATE.txt`

### D. Holdout discipline

- Add more starts as `holdout/h03_start.png`, `h04_…` (5+ total).
- **Never** put those same photos into `gold/` or `hard/` as training starts.
- Scorecard: `datasets/keep_outfit/scores/scorecard.csv`  
  Columns: `id,bucket,ckpt,face,garment,volume,photoreal,notes,pass` (1/0 per score column).

### E. Sources for more starts/targets

- Phone / web library keepers (download start + result)
- New local Comfy runs
- **Not** the 12-ref gallery as targets

---

## When gold is ready — train (exact)

Do this on the **GPU PC** (offline). Do not train through Render.

1. Confirm: `python scripts/keep_outfit_dataset_lint.py` reports gold ≥ 20 and holdout ≥ 5 with no caption issues.
2. Trainer: Kohya / OneTrainer (Flux Dev LoRA), base = same Flux Dev family Comfy already uses.
3. Start recipe (from train guide):
   - Rank **16–32**, alpha ≈ rank (or rank/2)
   - LR ~**1e-4** (UNet); batch **1** on 16GB
   - Res **768–1024**; ~**1–2k** steps on 20–50 pairs; stop if face/outfit collapses
4. Every **200–400** steps: copy checkpoint → run **all holdout starts** through the **real** keep-outfit graph (PuLID → mask → WIP LoRA → soft restore). Promote by **holdout pass rate**, not train loss.
5. Save winner, e.g.:

```text
E:\Comfy-Desktop\ComfyUI-Shared\models\loras\keep_outfit_reshape_v1.safetensors
```

(Adjust if Comfy models live elsewhere on that PC.)

6. Wire overlay (gitignored):

```text
private/lora_files.py
  breast_enhance → keep_outfit_reshape_v1.safetensors
```

Keep the logical id stable unless you add a new id only for clothed enhance in planner `params_hints.loras`.

7. Strength start band after wire: **0.6–0.85**. Re-score holdout + fixtures. Then:

```text
python scripts/sync_runtime_overlay.py
```

8. After a good custom LoRA, you can reduce reliance on Pass C paste / aggressive wrap — only after holdout still passes.

Full tables/checklist: [`KEEP_OUTFIT_LORA_TRAIN.md`](KEEP_OUTFIT_LORA_TRAIN.md).

---

## Product path already on `main` (inference)

| Piece | Value |
|-------|--------|
| Workflow | `keep_outfit_reshape.v1` |
| Task | `edit.keep_outfit_reshape` |
| Backbone | Flux Dev img2img (**not** Kontext ReferenceLatent) |
| Mask coverage | sampler `noise_mask` **12–20%** |
| Strap/hem | **post only** (`garment_restore_mask` / `restore_outside_chest`) |
| PuLID | `pulid_flux_v0.9.1.safetensors` (Pass A ~denoise 0.40, no reshape LoRA) |
| Pass B | masked reshape denoise **0.55–0.70** |
| Pass C | paste face/straps from **start** |
| Current reshape weight (front) | `Huge_natural_breasts_for_FLUX_v2.safetensors` (`breast_enhance`) until custom keep-outfit LoRA ships |
| Current reshape weight (back) | `FLUX_FD-LargeButt-SkinnyWaist-FP8.safetensors` (`ass_enhance` / `hip_enhance`) |
| Mask region | `bust` / `hip` / `curves` via `keep_outfit_edit_mask_png(region=…)` |
| Wrap | `fabric` |
| Planner denoise hint | **0.62** |
| Overlay LoRA strength | bust **0.72**, hip **0.70** |

Production: frontend `https://frontend-six-chi-37.vercel.app`, API `https://wan-studio-api.onrender.com`, repo `https://github.com/wellswenger-svg/Maal` `main`.

---

## Resume checklist (next PC)

1. [ ] `git pull` `origin main` on `wellswenger-svg/Maal`
2. [ ] Copy `private/` from this GPU PC (required — not in git) + `datasets/keep_outfit/` (+ secrets if needed)
3. [ ] Confirm overlay + weights: `overlay_status()` all True; `_find_weight(...)` finds front/back/unlock/PuLID
4. [ ] Point `.env` `COMFYUI_URL` at this PC’s Comfy (tunnel/LAN) if using remote GPU
5. [ ] Local Comfy + SAM: `models/sams/sam_vit_b_01ec64.pth` if using Impact SAM refine
6. [ ] Eval `holdout/h01_start.png` + `h02_start.png` (`enhance_boobs` / `enhance_ass`); fill `scores/scorecard.csv`
7. [ ] Near-term: mask/restore/denoise only — do **not** stack more Civitai bust LoRAs or PixAI
8. [ ] Add gold/hard pairs until lint is happy (20+ gold, 5+ holdout)
9. [ ] Train custom LoRA → **replace** `breast_enhance` in `private/lora_files.py` → holdout pass → `sync_runtime_overlay.py`
10. [ ] Freeze numbers only after fixtures pass; stop per-photo denoise chasing

---

## Key files

| Layer | Path |
|-------|------|
| This handoff | `KEEP_OUTFIT_CONTINUE.md` |
| Train protocol | `KEEP_OUTFIT_LORA_TRAIN.md` |
| Lab data | `datasets/keep_outfit/` |
| Dataset lint | `scripts/keep_outfit_dataset_lint.py` |
| Workflow | `backend/ai_engine/workflows/edit_suite/v1.py` |
| Mask / post | `backend/ai_engine/post/face_lock.py`, `pipeline.py`, `perception/garment_mask.py` |
| Graph + PuLID | `backend/workflows_wan.py`, `backend/comfy_client.py` |
| Overlay (gitignored) | `private/planner_rules.py`, `private/edit_runner.py`, `private/lora_files.py` |
| Overlay upload | `scripts/sync_runtime_overlay.py` |
| Tests | `backend/ai_engine/tests/test_keep_outfit_reshape.py` |

```text
python -m unittest backend.ai_engine.tests.test_keep_outfit_reshape backend.ai_engine.tests.test_kontext_graph backend.ai_engine.tests.test_phase7_hardening
python scripts/keep_outfit_dataset_lint.py
python scripts/sync_runtime_overlay.py
```

Optional remote eval (slower): `tmp_test/run_one.py` + preset `enhance_boobs` against `https://wan-studio-api.onrender.com` (`tokens&cmd`, PIN, owner `utester`). Prefer local Comfy first.

---

## Constraints

- Keep git/comments generic (`keep_outfit`, `clothed_enhance`). Graphic strings stay in `private/`.
- Never commit `tokens&cmd`, `.env`, or `private/`.
- Push auth: PAT from `tokens&cmd` (`github=`). No browser GitHub login.

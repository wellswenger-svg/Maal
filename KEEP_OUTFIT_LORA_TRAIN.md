# Keep-outfit LoRA training guide

How to get **one** reshape setting that works across many start photos — not a denoise that only fits one image.

## Why 0.84 / 0.82 on one photo is not training

Per-job knobs (denoise, LoRA strength) are **inference settings**. They are tuned to that photo’s lighting, crop, and fabric. They do **not** become the default for everyone.

| Approach | Generalizes? | Use for |
|----------|--------------|---------|
| Per-image denoise (e.g. 0.84) | No | Debug one hard case |
| Freeze defaults on 3–5 fixtures | Yes (product) | Ship keep-outfit |
| Train a Flux LoRA on many pairs | Yes (style/volume) | When frozen defaults still fail across bodies/clothes |

This repo has **no built-in trainer** and **no auto-train from phone uploads**.  
The lab protocol below is **manual** (you curate pairs → offline Kohya/OneTrainer → wire overlay).  
See **Automation** later for what a future pipeline could do with your inputs/demands — that is **not implemented** yet.

Training is done offline, then the `.safetensors` is dropped into Comfy and wired in the overlay.

## What you already have

- Reshape weight in use today: Flux LoRA mapped as `breast_enhance` → `Huge_natural_breasts_for_FLUX_v2.safetensors`
- Hip reshape (clothed back): `ass_enhance` / `hip_enhance` → `FLUX_FD-LargeButt-SkinnyWaist-FP8.safetensors`
- Keep-outfit path: `keep_outfit_reshape.v1` (img2img + mask + PuLID pass A + soft garment restore)
- Overlay strengths live in gitignored `private/edit_runner.py` / `private/lora_files.py`

Training a **custom** LoRA means **replacing** that reshape weight (not stacking another public bust LoRA, not PixAI).  
Decision table + current wiring checklist: [`KEEP_OUTFIT_CONTINUE.md`](KEEP_OUTFIT_CONTINUE.md) § *LoRA strategy* / *Model wiring*.

### Public sources — use how?

| Source | Use for keep-outfit? |
|--------|----------------------|
| **Civitai / HuggingFace** | Download pinned `.safetensors` into Comfy only (see `private/catalog_loras.py`). Do not call at runtime. |
| **PixAI** | **No** — hosted API; wrong stack for masked keep-outfit + PuLID. |
| **Stack extra public bust LoRAs** | **No** — fights cloth lock; prefer one reshape id. |
| **Your trained `keep_outfit_reshape_vN`** | **Yes** — replace `breast_enhance` mapping when holdout passes. |

## Goal of a proper keep-outfit LoRA

Teach Flux: **same person, same garment type/color, only change volume under cloth** (photoreal fabric drape).

Do **not** teach: become another person’s body/outfit from the 12-ref gallery.

---

## Lab protocol — structured, meaningful training

Treat this like a small lab, not “run Kohya once.” Structure beats more GPUs.

### What to train vs what to leave alone

| Piece | Train? | Role |
|-------|--------|------|
| Flux Dev base | No | Edit backbone |
| **Your reshape LoRA** | **Yes** | Volume under same cloth |
| Unlock / COF / wet LoRAs | No | Fixed stack for other presets |
| PuLID | No | Identity at inference (Pass A) |
| CLIPSeg / SAM | No | Garment masks, not style |
| Second “identity” LoRA | Rare | Only if faces still drift after PuLID |
| Wan / video LoRAs | No | Wrong task for keep-outfit |
| IP-Adapter on ref gallery | No | Pulls other identities/outfits |

One clear LoRA verb: **volume under same cloth**. Mixing nude/pose/undress into this weight destroys keep-outfit clarity.

### Dataset buckets (required layout)

| Bucket | Purpose | Train on it? |
|--------|---------|--------------|
| **A – gold** | Best pairs: face+clothes locked, fabric photoreal | Yes (core) |
| **B – hard** | Dark shirts, straps, hands in frame, side light, busy bg | Yes (anti-overfit) |
| **C – holdout** | Same scoring photos, **never** in training | No — final judge only |
| **Neg / reg** | Start ≈ target; caption “same clothes, no reshape” | Yes, low weight |

Targets:

- Gold: **20–50** pairs minimum  
- Hard: at least ~20–30% of gold count  
- Holdout: **5+** starts (can reuse Phase 0 fixtures)  
- Neg/reg: a handful is enough  

Near-duplicates of one person/outfit do **not** count as diversity.

### Suggested folder layout (GPU PC)

```text
datasets/keep_outfit/
  gold/
    001_start.png
    001_target.png
    001.txt                 # caption
    ...
  hard/
    ...
  holdout/
    h01_start.png           # no targets needed; eval only
    ...
  reg/
    r01_start.png
    r01_target.png          # often same as start
    r01.txt                 # "same clothes, no reshape, photoreal"
  scores/
    scorecard.csv           # see below
  checkpoints/              # copies of promising .safetensors
    keep_outfit_reshape_v1_step0800.safetensors
    ...
```

Keep this tree **off git** (large PNGs). Only document paths here.

### Caption contract (one template)

Gold / hard — always the same pattern:

```text
photo of a woman, keep same clothes, volume under cloth, fabric may drape, photoreal
```

Optional on-switch trigger (use in **every** gold/hard caption if you adopt it):

```text
korfit, photo of a woman, keep same clothes, volume under cloth, photoreal
```

Reg / neg:

```text
photo of a woman, same clothes, no reshape, photoreal
```

Do not invent long per-image novels. The LoRA should learn one edit, not a story.

### Score sheet (fixed rubric)

Score **0 or 1** per column. Pass = all four **1**, or face+garment **1** and volume **1** with seams **0** only if you are debugging masks (do not ship).

| id | bucket | ckpt / strength | face | garment | volume | seams_ok | notes | pass |
|----|--------|-----------------|------|---------|--------|----------|-------|------|
| h01 | holdout | v1@0.70 | 1 | 1 | 1 | 1 | | Y |
| f02 | fixture | baseline | 1 | 0 | 1 | 0 | two-tone neckline | N |

Definitions:

| Column | 1 means |
|--------|---------|
| face | Same face / hair / identity as start |
| garment | Same garment type and color; not a new outfit |
| volume | Visible but photoreal shape change under cloth |
| seams_ok | No rectangle, two-tone patch, melted sleeves, sticker straps |

CSV header for `scores/scorecard.csv`:

```text
id,bucket,checkpoint,strength,denoise,face,garment,volume,seams_ok,notes,pass
```

### Checkpoint rules (pick winners by holdout)

1. Train on **gold + hard + reg** only.  
2. Every N steps (e.g. 200–400), copy a checkpoint and run **all holdout starts** through the real keep-outfit graph:
   - Pass A: PuLID, low denoise  
   - Pass B: mask + WIP LoRA  
   - Pass C: soft face/strap restore  
3. Fill the score sheet.  
4. **Keep the checkpoint with the best holdout pass rate**, not the lowest training loss.  
5. If face or garment score drops while volume rises → overfit / too strong — stop, lower LR/rank/steps, or add reg pairs.  
6. Never promote a ckpt that fails holdout even if gold looks perfect.

### Versioning

| File | Meaning |
|------|---------|
| `keep_outfit_reshape_v1.safetensors` | First ship candidate |
| `…_v2.safetensors` | Trained on v1 failure modes (e.g. more dark tops / straps) |
| Do not overwrite v1 until v2 beats holdout | Always keep the previous winner |

Inference strength stays **0.6–0.85**. If you need **>1.0** to see an effect, the LoRA failed — fix data/train, don’t crank the slider.

### Inference stack that makes training meaningful

Training only helps if inference is frozen the same way every eval:

1. Denoise band **0.55–0.70** (not per-photo 0.84)  
2. Garment ∩ bust mask (CLIPSeg / local fabric)  
3. PuLID on Pass A only; reshape LoRA on Pass B only  
4. Soft post restore  

If seams fail with different failure modes photo-to-photo → fix **mask/post**, not more epochs.

### Decision tree (lab)

```text
One photo looks bad at frozen defaults?
  → Debug that photo / mask only (not a new global denoise)

Holdout fails the same way (weak volume / fabric melt)?
  → Add gold/hard pairs of that failure → train v2

Holdout fails differently (seams, wrong shirt region)?
  → Fix garment mask / feather — training will not fix a bad mask

Gold perfect, holdout poor?
  → Overfit — more diversity, more reg, lower rank/steps; discard that ckpt
```

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

Use the **Lab protocol** buckets above (`gold` / `hard` / `holdout` / `reg`). Details below are the pair format inside those folders.

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

## Automation — what exists vs what you asked for

### Direct answer

| Question | Answer |
|----------|--------|
| Does this doc describe an auto system that reads my inputs/demands, fetches missing pieces, and trains? | **No — not previously; this section defines it as a future design.** |
| Does the app do that today? | **No.** Phone jobs only **infer** (edit one image). They do not collect datasets or run Kohya. |
| Can that be built later? | **Yes**, as a **GPU-PC lab script/pipeline**, not inside every phone request. |

Training on every user upload would be slow, expensive, easy to overfit, and unsafe for “one bad denoise → new global LoRA.” Automation should run **offline batches** from curated inputs you approve.

### What “your inputs / demands” means

| You provide | System uses it for |
|-------------|-------------------|
| Start photos (`*_start.png`) | Training input / holdout |
| Liked outputs (`*_target.png`) you marked good | Training targets (gold/hard) |
| Short demand / caption template (or default keep-outfit line) | Captions for all pairs |
| Score rubric (face / garment / volume / seams) | Auto or semi-auto pass/fail |
| Frozen inference band (denoise + strength) | Eval graph must match production |

Refs gallery = **QA look** only, never auto-targets.

### What automation **should** do (design — not built)

A lab runner on the GPU PC (e.g. future `scripts/keep_outfit_train_lab.py`) would:

1. **Ingest**  
   - Scan `datasets/keep_outfit/{gold,hard,holdout,reg}/`  
   - Pair `###_start` ↔ `###_target`  
   - Apply the caption contract (or your demand string)

2. **Need-check (gate before train)**  
   - Count gold ≥ 20? hard present? holdout ≥ 5?  
   - Base Flux weight present? Comfy up? Disk free?  
   - SAM/CLIPSeg optional for **eval masks**, not for training itself  
   - If anything missing → **stop and print a checklist** (do not start a half train)

3. **Train**  
   - Call external trainer (Kohya/OneTrainer CLI) with fixed recipe (rank 16–32, batch 1, …)  
   - Write checkpoints under `datasets/keep_outfit/checkpoints/`

4. **Eval loop**  
   - Every N steps: run holdout starts through **real** keep-outfit (PuLID → mask → WIP LoRA → soft restore)  
   - Fill `scores/scorecard.csv`  
   - Keep best **holdout** pass rate

5. **Promote or refuse**  
   - If holdout ≥ threshold (e.g. 4/5 pass) → copy to Comfy `models/loras/keep_outfit_reshape_vN.safetensors` and print overlay wire steps  
   - Else → **do not** overwrite production LoRA; report failures (mask vs volume)

6. **Never auto-write production overlay** without a human confirm (or a `--promote` flag you pass deliberately)

### What automation must **not** do

- Train from a single phone job “because denoise 0.84 looked good”  
- Pull 12-ref identities as targets  
- Download random LoRAs from the internet without a pin  
- Change Render overlay secrets unattended  
- Replace Flux / Wan bases as part of “keep-outfit train”

### Staged roadmap (if you implement later)

| Stage | Automate | Still human |
|-------|----------|-------------|
| **S0** | Folder + caption lint; print “ready / not ready” | Curate gold targets |
| **S1** | Need-check + launch trainer CLI | Install trainer once |
| **S2** | Holdout eval via Comfy API + scorecard CSV | Spot-check seams visually |
| **S3** | Optional `--promote` → copy LoRA + remind `sync_runtime_overlay` | Approve promote |

Until S1+ exists, use this doc as the **manual** procedure. Do not expect the phone UI or Render API to “train when I demand.”

### Relation to phone “training” you did earlier

Chasing 0.84 / 0.82 on one library image was **inference tuning**.  
Automation of **that** would be wrong.  
Automation of **dataset → LoRA → holdout → promote** is the meaningful path — and it is **specified here, not shipped**.

---

## Training on this GPU PC + media from the web

Your intended setup is correct for hardware:

| Where | What runs |
|-------|-----------|
| **This PC** (Comfy / 16GB GPU) | Offline LoRA train + holdout eval through local Comfy |
| **Other PC / phone** | UI only; does not need the trainer |
| **Web** | Optional **source of files you download onto this PC** — not live training over the network |

Pull media **onto disk first** (`datasets/keep_outfit/...`), then train locally. Do not stream-train from URLs.

### Good vs bad web media for keep-outfit

| OK | Not OK |
|----|--------|
| Your own library exports (start + liked output) mirrored to this PC | Random “similar body” stills with **no** matching start photo |
| Pairs you generated here, then copied into `gold/` / `hard/` | Using the **12-ref gallery as targets** (other identities/outfits) |
| Stock / licensed stills **only** if you also have a clear start→edit story (rare) | Scraping social images of real people without rights / consent |
| Holdout starts pulled from the same library API as files | Training on unzipped junk with no captions / no pairing |

Best path: on the web UI or Render library, download **start + good result** for each keeper job, save as `###_start.png` / `###_target.png` on this PC, caption with the contract, then train here.

Web “inspiration” images alone do **not** teach “edit *this* photo.” You need **paired** start→target.

### Practical workflow on this machine

1. Create `datasets/keep_outfit/{gold,hard,holdout,reg,scores,checkpoints}/` on a fast disk (e.g. under `D:\` or next to Comfy).  
2. From phone/web library: download keepers → drop into `gold/` or `hard/`; put aside 5+ starts in `holdout/` with **no** training use.  
3. Write one caption file per pair (template in Lab protocol).  
4. Run Kohya / OneTrainer **on this PC**, base = Flux Dev weights already in Comfy shared models.  
5. Every N steps: point Comfy at the WIP LoRA, score **holdout** on this same PC.  
6. Promote winner into `E:\Comfy-Desktop\ComfyUI-Shared\models\loras\`, wire `private/`, `sync_runtime_overlay.py` when ready for phone.

Render/Vercel stay for **inference** after promote. Training traffic should not go through Render.

### Rights / policy note

Only use media you have rights to use for training (your generations, your uploads, properly licensed sets). Do not build a scrape pipeline that assumes “on the web = free to train.” Product policy and platform ToS still apply.

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

### Lab / data
- [ ] Folders: `gold/`, `hard/`, `holdout/`, `reg/`, `scores/`
- [ ] 20+ gold pairs, some hard, 5+ holdout starts, a few reg pairs
- [ ] One caption template (optional `korfit` trigger consistent)
- [ ] No ref-gallery identities as targets
- [ ] `scorecard.csv` ready

### Train / select
- [ ] Rank 16–32; batch 1 on 16GB
- [ ] Eval holdout every N steps on the **real** keep-outfit graph
- [ ] Promote ckpt by **holdout** pass rate, not train loss
- [ ] Versioned file under Comfy `models/loras/` (do not clobber previous winner)

### Ship
- [ ] Phase 0 fixtures frozen with one denoise + one strength  
- [ ] Overlay `lora_files` + strength (0.6–0.85) updated; `sync_runtime_overlay.py` run  
- [ ] Holdout + fixtures re-scored; strength frozen  
- [ ] Per-photo denoise chasing left as debug only  

### Automation (future — not in repo yet)
- [ ] Understand: no auto-train from phone demands today  
- [ ] Optional later: S0 lint → S1 trainer CLI → S2 holdout scorecard → S3 manual `--promote`  

## Related

- Handoff / eval: [`KEEP_OUTFIT_CONTINUE.md`](KEEP_OUTFIT_CONTINUE.md)  
- Production URLs: [`PRODUCTION_URLS.md`](PRODUCTION_URLS.md)  
- Models catalog notes: [`MODELS.md`](MODELS.md)

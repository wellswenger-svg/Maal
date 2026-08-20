# Keep-outfit reshape — where to continue

Last machine: Windows (`d:\YtAuto\contrnt`), 2026-08-19.

Tracked code for `keep_outfit_reshape.v1` is on `main`. **Gitignored overlay** (`private/`) is **not** in git. Copy that folder to the other PC, or re-upload it to Render with `python scripts/sync_runtime_overlay.py` after overlay edits.

Do **not** edit `.cursor/plans/keep-outfit_edit_quality_6312ed4d.plan.md`.

## Done on this branch

- Workflow `keep_outfit_reshape.v1` / task `edit.keep_outfit_reshape` (preferred Flux Dev img2img, **not** Kontext ReferenceLatent).
- Planner overlay maps clothed body-enhance (`reason=clothed_body_enhance_pattern`) to that task. Tracked fallback: `edit.keep_outfit_reshape` → `edit.general_instruction` if the workflow is missing.
- Sampler `noise_mask` target **12–20%** coverage. Strap/hem restore is **post only** (`garment_restore_mask` / `restore_outside_chest`), not subtracted from the sampler mask.
- PuLID nodes in `build_i2i_prompt` (`pulid_file=pulid_flux_v0.9.1.safetensors`). Overlay Pass A: denoise ~0.40 + PuLID, no reshape LoRA. Pass B: masked reshape denoise **0.55–0.70**. Pass C: paste original face/straps from the **start** photo.
- Overlay reshape LoRA strength **0.72**. Prompt wrap mode **`fabric`** (keep garment type/color; allow drape). Planner denoise hint **0.62**.
- Unit tests: `backend/ai_engine/tests/test_keep_outfit_reshape.py`, extra cases in `test_kontext_graph.py`.

## Not done (resume here)

1. **Eval the same two start photos** after garment-mask wiring (CLIPSeg / local fabric ∩ bust core; soft seam restore). Score: same face/hair/bg, same garment type/color, photoreal volume, no rectangle/two-tone smear.
2. **SAM weight installed** on this GPU PC: `models/sams/sam_vit_b_01ec64.pth` (Impact `SAMLoader`). CLIPSeg nodes are used for cloth text masks; SAM is available for further refine if needed.
3. **Overlay sync:** `python scripts/sync_runtime_overlay.py` after `private/planner_rules.py` / `private/edit_runner.py` changes.
4. **Confirm production path:** Vercel → Render → Cloudflare tunnel → Comfy `:8188`.
5. **Freeze** LoRA/denoise/mask numbers only after three fixtures pass.

For training a custom reshape LoRA that generalizes across photos (not per-image denoise), see [`KEEP_OUTFIT_LORA_TRAIN.md`](KEEP_OUTFIT_LORA_TRAIN.md).

## Key files

| Layer | Path |
|--------|------|
| Workflow | `backend/ai_engine/workflows/edit_suite/v1.py` |
| Planner fallback | `backend/ai_engine/planner/__init__.py` |
| Mask / post | `backend/ai_engine/post/face_lock.py`, `pipeline.py`, `perception/garment_mask.py` |
| Graph + PuLID | `backend/workflows_wan.py`, `backend/comfy_client.py` |
| Overlay (gitignored) | `private/planner_rules.py`, `private/edit_runner.py` |
| Overlay upload | `scripts/sync_runtime_overlay.py` |
| Tests | `backend/ai_engine/tests/test_keep_outfit_reshape.py` |

## Commands

```text
python -m unittest backend.ai_engine.tests.test_keep_outfit_reshape backend.ai_engine.tests.test_kontext_graph backend.ai_engine.tests.test_phase7_hardening
python scripts/sync_runtime_overlay.py
```

Eval shortcut on a machine with Comfy + overlay: preset id used last was `enhance_boobs` via `tmp_test/run_one.py` against `https://wan-studio-api.onrender.com` (needs `tokens&cmd`, PIN token, tester owner `utester`). Prefer local Comfy first so you are not waiting on Render for Pass A+B.

## Constraints

- Keep git/comments generic (`keep_outfit`, `clothed_enhance`). Graphic strings stay in `private/`.
- Never commit `tokens&cmd`, `.env`, or `private/`.
- Production: frontend `https://frontend-six-chi-37.vercel.app`, API `https://wan-studio-api.onrender.com`, repo `wellswenger-svg/Maal` `main`.
- Push auth: PAT from gitignored `tokens&cmd` (`github=`). Do not use browser GitHub login.

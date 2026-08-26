# Keep-outfit training lab (local)

Paired start→target data for a custom Flux reshape LoRA.  
Full protocol: [`../../KEEP_OUTFIT_LORA_TRAIN.md`](../../KEEP_OUTFIT_LORA_TRAIN.md).

PNGs are gitignored (`*.png`). This README / CSV templates are tracked.

## Layout

| Folder | Role |
|--------|------|
| `gold/` | Best clothed keep-outfit pairs (`###_start.png` + `###_target.png` + `###.txt`) |
| `hard/` | Same format; dark shirts, straps, hands, hard light |
| `holdout/` | Starts **only** — never train on these |
| `reg/` | Near-identity pairs (start≈target), “no reshape” captions |
| `scores/` | `scorecard.csv` |
| `checkpoints/` | WIP `.safetensors` copies |
| `staging/starts/` | Starts waiting for a good target |
| `staging/rejected_notes/` | Why local eval outs were not gold |

## Seeded on this PC (2026-08-26)

| Path | Source | Use |
|------|--------|-----|
| `holdout/h01_start.png` | `tmp_test/first_preset_run/input_1.png` (black tank + white shirt) | Eval only |
| `holdout/h02_start.png` | `tmp_test/first_preset_run/input_2.png` (blue crop) | Eval only |
| `staging/starts/s01_*.png` / `s02_*.png` | Same two starts | Pair when you get a **clothed** keeper |

**Gold is empty on purpose.** Local `tmp_test` outs were rejected (see `staging/rejected_notes/AUDIT.md`).

## Caption contract (every gold/hard pair)

```text
photo of a woman, keep same clothes, volume under cloth, fabric may drape, photoreal
```

Optional on-switch (use in **every** gold/hard caption if adopted):

```text
korfit, photo of a woman, keep same clothes, volume under cloth, photoreal
```

Reg:

```text
photo of a woman, same clothes, no reshape, photoreal
```

## How to add a gold pair

1. Run keep-outfit (local Comfy preferred) on a start that is **not** already in `holdout/`.
2. Keep only if: same face/hair/bg, same garment type/color, photoreal volume, **no** rectangle / two-tone paste / nude swap.
3. Save as next free id, e.g. `gold/003_start.png`, `gold/003_target.png`, `gold/003.txt`.
4. Aim for **20–50** gold before training; add ~20–30% hard.

## Never put in gold/hard targets

- Ref-gallery bodies / outfits (`tmp_test/maxref_run/ref_*.png`)
- Nude / undress / identity-swap outs
- Visible rectangular paste patches
- Melted neckline / wrong shirt color

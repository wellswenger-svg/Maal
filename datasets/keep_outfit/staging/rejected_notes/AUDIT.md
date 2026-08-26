# Local tmp_test audit — not used as gold (2026-08-26)

| Candidate | Verdict | Why |
|-----------|---------|-----|
| `first_preset_run/out_1.png`, `out_2.png` | Reject | Nude / body identity drift; teaches undress, not keep-outfit |
| `maxref_run/ref_1.png` … `ref_3.png` | Reject as targets | Other identities / outfits (gallery). OK as human QA refs only |
| `maxref_run/out_r2_*` … `out_r4_*` | Reject | Visible rectangular torso paste / garment mismatch (the workaround) |
| `maxref_run/out_1.png`, `out_2.png` | Hold | Clothes roughly kept; volume change too weak / unclear to train on. Re-run keep-outfit and only promote if fabric+volume clearly pass |

Training targets must be **same person, same garment, volume under cloth**. Paste-gallery and nude outs poison the LoRA.

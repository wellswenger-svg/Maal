# Add-workflow modularity checklist

Companion to [WORKFLOWS.md](WORKFLOWS.md) §7. Use this for every new `workflow_ref`.

## Checklist

1. [ ] Implement builder under `backend/ai_engine/workflows/{id}/vN.py`
2. [ ] Register `WorkflowRecord` with **all** required fields (profiles Draft–Ultra, `enabled` / `beta` / `experimental`, preferred / compatible / minimum models)
3. [ ] Ensure referenced `model_id`s exist in Model Manager catalog
4. [ ] Set `fallback_workflow_ref`
5. [ ] Add `task_types` mapping (Planner emits `task_type` only — never hardcode workflow names in Planner/API)
6. [ ] Ship with `enabled: false` **or** `experimental: true` / `beta: true` until fixtures pass
7. [ ] Add fixture + runtime benchmark row; set `benchmark_estimated: false` when measured
8. [ ] Kill-switch test: flip `enabled=false` and confirm resolve skips the ref

**Do not** edit unrelated workflow modules.

---

## Dry-run: `video_v2v.experimental` (Phase 7)

Executed 2026-08-06 as the expansion-hook dry-run.

| Step | Result |
|------|--------|
| 1. Builder | Stub runner in `workflows/experimental/stubs.py` (raises `EXPERIMENTAL_STUB`) |
| 2. Full metadata | Draft–Ultra profiles, preferred/compatible/minimum Wan models |
| 3. Models in catalog | `video.wan22_*` present |
| 4. Fallback | `video_i2v.v1` |
| 5. task_types | `video.v2v` (not emitted by stable rules; experimental channel only) |
| 6. Flags | `experimental=true`, `channel=experimental`, `enabled=true` |
| 7. Score | `benchmark_score=0`, `benchmark_estimated=true` until implemented |
| 8. Kill switch | Set `enabled=false` on the record without redeploying graphs |

Same pattern applied to `video_extend.experimental` (`task_type=video.extend`).

Stable channel resolve **must not** return these refs (covered by Phase 7 unit tests).

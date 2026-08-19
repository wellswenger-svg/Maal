# AI Engine — Implementation Plan

**Status:** Phase 0–**7** complete (engine operable; experimental stubs + scorecards)  
**Architecture refs:** [AI_ENGINE.md](AI_ENGINE.md) · [WORKFLOWS.md](WORKFLOWS.md) · [MODELS.md](MODELS.md)

**Priority lock:** P0 docs → P1 Image Editing Engine → P2 Image-to-Video Engine  

**Claims policy:** Exit criteria are **measurable** (runtime, VRAM, IoU, identity cosine, success rate). No “ChatGPT/Kling quality” gates.

---

## Phase 0 — Architecture freeze (current)

| | |
|--|--|
| **Purpose** | Lock module boundaries, registries, routing, profiles, recovery, model choices |
| **Files** | `AI_ENGINE.md`, `WORKFLOWS.md`, `MODELS.md`, `IMPLEMENTATION_PLAN.md`; plan file `ai_engine_architecture_8febe6f4.plan.md` |
| **Complexity** | High (design/research) |
| **Dependencies** | None |
| **Expected output** | Reviewable architecture pack |
| **Exit criteria** | Stakeholder approval of docs; no code started |
| **Risks** | Model landscape drift — pin versions + review date in MODELS.md |

---

## Phase 1 — Engine skeleton + registries (behavior-preserving)

| | |
|--|--|
| **Purpose** | Insert `backend/ai_engine/` behind `POST /api/generate` without changing output quality yet |
| **Files affected** | New `backend/ai_engine/**`; thin adapter in `backend/main.py`; wrap existing builders from `backend/workflows_wan.py` as `image_img2img.v0_legacy` + `video_i2v.v0_legacy` |
| **Complexity** | Medium |
| **Dependencies** | Phase 0 approval |
| **Expected output** | All generates go Planner(rules-only stub) → Registry → ModelManager(noop ensure) → ExecutionEngine → same Flux/Wan graphs as today |
| **Exit criteria** | Golden outputs match pre-engine baseline on fixture set; registry resolve covered by unit tests; **zero hardcoded workflow names** in adapter |
| **Potential risks** | Regression in generate path — mitigate with fixture hashes |

---

## Phase 2 — Rule Engine + conditional VLM

| | |
|--|--|
| **Purpose** | Real Planner: Rule Engine bypass for upscale / bg remove / img2img / i2v; VLM only when ambiguous/multi-step |
| **Files affected** | `ai_engine/planner/rules.py`, `vlm.py`, `schema.py`; Model Manager slot `planner.default_model` → initial VLM weight; VRAM unload hooks in `runtime/vram.py` |
| **Complexity** | High |
| **Dependencies** | Phase 1; disk for VLM weights |
| **Expected output** | ExecutionPlans with `planner_path` rules|vlm; Developer Mode override only |
| **Exit criteria** | ≥95% correct bypass on labeled simple prompts; VLM unload frees ≥90% of VLM-reserved VRAM before gen (nvidia-smi / torch); ambiguous set invokes VLM ≥90% |
| **Potential risks** | Misclassification — confidence threshold + logging; VLM OOM — quant + sequential policy |

---

## Phase 3 — Model Manager + Error Recovery core

| | |
|--|--|
| **Purpose** | Full model registry records; ensure/missing; replacement candidates; OOM/load-fail/retry/corrupt handlers |
| **Files affected** | `ai_engine/models/**`, `runtime/recovery.py`, `runtime/vram.py` (cache budget); health endpoint fields (optional) |
| **Complexity** | Medium–High |
| **Dependencies** | Phase 1 (Phase 2 can parallelize carefully) |
| **Expected output** | `/api/health` or engine health lists missing required models per enabled workflows; OOM degrade path tested |
| **Exit criteria** | Forced OOM test survives process + degrades profile or fallback; missing model returns actionable download_source; corrupt empty output rejected 100% on fixtures |
| **Potential risks** | False OOM triggers — calibrate thresholds on 5060 Ti |

---

## Phase 4 — Perception stack ✅

| | |
|--|--|
| **Purpose** | GroundingDINO + SAM2 + BiRefNet adapters for surgical masks/mattes |
| **Files affected** | `ai_engine/perception/**`; `workflows/background_remove/v1`; model catalog slots; engine wire-up |
| **Complexity** | Medium–High |
| **Dependencies** | Phase 3 |
| **Expected output** | Mask/matte artifacts on `plan.perception`; `background_remove.v1` runnable (rembg or heuristic degrade) |
| **Exit criteria** | Mean mask IoU ≥ **0.70** on internal fixture set *(pending GPU weights)*; bg-remove Draft p50 ≤ **15s** with rembg |
| **Potential risks** | Detector miss → `mask_failed` / `perception_degraded` warnings; Comfy BiRefNet/SAM hooks stubbed until nodes+weights installed |
| **Implemented** | Heuristic grounding + box masks; rembg matting when installed; engine passes `perception` into runners; health lists perception models |

---

## Phase 5 — P1 Image Editing Engine ✅

| | |
|--|--|
| **Purpose** | Ship versioned workflows: clothing/object/bg/inpaint/outpaint/face/hair/product/style/identity/upscale/restore + Draft–Ultra profiles |
| **Files affected** | `ai_engine/workflows/edit_suite/v1.py`, `_shared/*`, `post/pipeline.py`, `comfy_client` profile overrides |
| **Complexity** | Very High |
| **Dependencies** | Phases 2–4 |
| **Expected output** | Task-specific pipelines selected via registry from `task_type` |
| **Exit criteria** | Outside-mask pixel delta ≤ **3%** on masked fixtures *(color_match post)*; face identity cosine ≥ **0.55** *(pending PuLID graph)*; Balanced image edit p50 ≤ **2.5 min**; success rate ≥ **95%** excluding bad inputs; license gate for Kontext NC enforced in meta |
| **Potential risks** | VRAM spikes on Ultra — invalid if peak &gt; ~14GB estimate; license compliance |
| **Implemented** | All P1 `task_type`s resolve to `*.v1` workflows; Flux img2img-backed runners with task prompts + profiles; perception deps; `color_match` outside-mask preserve; Kontext/Fill/FaceDetailer/ReActor graphs still deferred (bind falls back to Dev + warnings) |

---

## Phase 6 — P2 Image-to-Video Engine ✅

| | |
|--|--|
| **Purpose** | Rebuild `video_i2v` (not v0_legacy): profiles, motion hints, VAE A/B, interp, upscale, encode; LightX2V Draft path |
| **Files affected** | `workflows/video_i2v/v1.py`, `motion.py`; `comfy_client` video overrides; post RIFE/upscale hooks |
| **Complexity** | Very High |
| **Dependencies** | Phase 5 stable enough; Wan weights present |
| **Expected output** | Profiled I2V with measurable improvement vs legacy |
| **Exit criteria** | Start-frame LPIPS improved ≥ **20%** vs `video_i2v.v0_legacy` on fixtures *(pending GPU fixture run)*; Balanced p50 ≤ **10 min** or documented waiver; Quality includes 16→24 interp intent; process survival 100% under OOM degrade |
| **Potential risks** | Sync HTTP timeouts — document shell async as follow-up (not blocking AI-layer design); 16GB res limits |
| **Implemented** | `video_i2v.v1` preferred over legacy (fallback=`v0_legacy`); Draft–Ultra length/steps/fps/shift/res; motion scaffold + planner `params_hints.motion`; Quality/Ultra post stages annotate RIFE 16→24 / frame upscale (Comfy RIFE graph pending `video.rife`); LightX2V Draft hint when LoRA missing |

---

## Phase 7 — Hardening + expansion hooks ✅

| | |
|--|--|
| **Purpose** | Benchmark score population; profile tuning; experimental channel; design-only registration stubs for `video_v2v` / `video_extend` |
| **Files affected** | `ops/scorecard.py`; `workflows/experimental/stubs.py`; `ADD_WORKFLOW_CHECKLIST.md`; health summary + footer; MODELS.md §8 |
| **Complexity** | Medium |
| **Dependencies** | Phases 5–6 |
| **Expected output** | Operable engine with estimated scorecards; disk report on `/api/health`; experimental stubs |
| **Exit criteria** | All P1/P2 stable workflows have `benchmark_score` (estimated until fixtures); disk footprint documented; add-workflow checklist dry-run for `video_v2v.experimental` |
| **Potential risks** | Disk growth — monitor shared model store |
| **Implemented** | Scorecard stamp on bootstrap; experimental `video_v2v` / `video_extend` stubs; checklist dry-run doc; health `summary.footer` for UI |

---

## Cross-phase constraints

1. **Never hardcode workflow names** in Planner or `main.py` — only `task_type` + registry resolve (Developer Mode exception).  
2. **Never hardcode planner VLM vendor ids** — only slot `planner.default_model`.  
3. **Strict module separation** — PR review rejects mixed responsibilities.  
4. **Every new workflow** ships all four profiles, feature flags (`enabled`/`beta`/`experimental`), preferred/compatible/minimum models, + required registry metadata (WORKFLOWS.md §1).  
5. **Sequential VRAM** on 5060 Ti 16GB mandatory in Execution Engine / Model Manager.  
6. **Error recovery** from AI_ENGINE.md §10 required before declaring a phase done.  
7. **Kill switch:** set `enabled: false` on a broken workflow_ref without redeploying graph code.

---

## Suggested implementation order (calendar-agnostic)

```
Phase0 (docs approve)
  → Phase1 (skeleton)
  → Phase3 (model manager + recovery) ─┐
  → Phase2 (rules + VLM)             ─┴→ Phase4 (perception)
                                         → Phase5 (P1 edits)
                                         → Phase6 (P2 I2V)
                                         → Phase7 (harden)
```

Phase 2 and 3 may overlap after Phase 1 if staffing allows; Phase 4 must not start without recovery/unload primitives.

---

## Non-goals until later shell work

- Frontend redesign  
- Auth / multi-tenant  
- Full async job queue / progress WS (note as dependency for Ultra I2V UX)  
- Replacing Mongo GridFS or scrub policy  

---

## Approval checklist

- [ ] AI_ENGINE.md module boundaries accepted  
- [ ] Rule-before-VLM + bypass list accepted  
- [ ] `planner.default_model` slot (no hardcoded Qwen id in architecture code) accepted  
- [ ] Workflow versioning + Draft/Balanced/Quality/Ultra accepted  
- [ ] preferred/compatible/minimum model tiers accepted  
- [ ] Feature flags `enabled` / `beta` / `experimental` accepted  
- [ ] Model registry fields + comparison selections accepted  
- [ ] Error recovery matrix accepted  
- [ ] Measurable exit criteria accepted (no marketing parity claims)  
- [ ] **Then** authorize Phase 1 coding  

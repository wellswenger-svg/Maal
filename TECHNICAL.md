# Wan Studio — Technical Architecture

This document describes the **system architecture**, **data flow**, **modules**, and **deployment topology** of Wan Studio so you can map the codebase to how the product actually runs.

> **AI Generation Layer (new):** see [AI_ENGINE.md](AI_ENGINE.md), [WORKFLOWS.md](WORKFLOWS.md), [MODELS.md](MODELS.md), [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Generation now routes through `backend.ai_engine` (registry + planner); Phase 1 still executes the same Flux/Wan Comfy graphs via legacy workflow runners.

---
     

**Wan Studio** is a thin orchestration layer around **ComfyUI** for:

| Mode | Model stack | Purpose |
|------|-------------|---------|
| `img` | **Flux Dev** (img2img) | Identity-preserving image edits from a start photo + prompt |
| `vid` | **Wan 2.2 I2V 14B** (dual-stage) | Image-to-video with the start frame locked |

**Design principle:** generated media is persisted **only in MongoDB GridFS**. Local ComfyUI input/output/temp files are scrubbed after each job (“zero residue”). There is **no auth, payments, scheduling, or YouTube upload** in this repo.

Product surface:

- FastAPI title: `Wan Studio` (`backend/main.py`)
- UI brand: Wan (`frontend/src/App.jsx`)

---

## 2. High-level architecture

```
┌─────────────────┐     HTTPS / REST      ┌──────────────────────┐
│  Browser (SPA)  │ ────────────────────► │  FastAPI (Render)    │
│  React + Vite   │ ◄──────────────────── │  orchestration API   │
│  (Vercel)       │   JSON + media bytes  │                      │
└─────────────────┘                       └──────────┬───────────┘
                                                     │
                          ┌──────────────────────────┼──────────────────────────┐
                          │                          │                          │
                          ▼                          ▼                          ▼
                 ┌─────────────────┐      ┌─────────────────┐      ┌────────────────────┐
                 │  MongoDB Atlas  │      │  ComfyUI (local) │      │ Google Translate   │
                 │  generations +  │      │  :8188 + GPU     │      │ (deep-translator)  │
                 │  GridFS media   │      │  often via       │      │ prompt → English   │
                 └─────────────────┘      │  Cloudflare      │      └────────────────────┘
                                          │  tunnel           │
                                          └─────────────────┘
```

**Roles**

| Layer | Responsibility |
|-------|----------------|
| **Frontend** | Upload image, prompt, mode; show result; library CRUD UI |
| **API** | Validate, normalize prompt, drive ComfyUI, store bytes in GridFS, scrub disk |
| **ComfyUI** | Actual GPU inference (Flux / Wan graphs) |
| **MongoDB** | Job metadata + binary media (single source of truth for outputs) |

There is **no app-level WebSocket** between browser and API. WebSockets exist only between **API ↔ ComfyUI** (job completion). Generation is **synchronous** on `POST /api/generate` (request can run for minutes).

---

## 3. Repository layout

```
contrnt/
├── backend/                 # FastAPI application
│   ├── main.py              # App entry, HTTP routes, optional SPA mount
│   ├── config.py            # pydantic-settings (env → typed settings)
│   ├── db.py                # Motor/Mongo + GridFS + generations CRUD
│   ├── comfy_client.py      # Upload → queue → WS wait → fetch → scrub
│   ├── workflows_wan.py     # ComfyUI workflow JSON builders (Flux / Wan)
│   ├── prompt_fix.py      # Typo/Hinglish cleanup, translate, edit/motion framing
│   └── scrub.py             # Secure wipe of wan_* ComfyUI artifacts
├── frontend/                # React + Vite SPA
│   ├── src/App.jsx          # Entire studio UI (generate + library)
│   ├── src/api.js           # REST client for /api/*
│   ├── src/index.css        # Styles
│   └── vite.config.js       # Dev proxy /api → :8000
├── comfy_nodes/             # Optional custom ComfyUI node pack (not used by current graphs)
├── run.py                   # Local: python run.py → uvicorn
├── requirements.txt         # Python deps
├── .env.example             # Backend env template
├── render.yaml              # Render Blueprint (API)
├── vercel.json              # Vercel monorepo build (SPA)
└── TECHNICAL.md             # This file
```

---

## 4. Technology stack

### Frontend

| Concern | Choice |
|---------|--------|
| UI | React **19.2** |
| Build | Vite **8** + `@vitejs/plugin-react` |
| Routing | None — single-page `App` |
| State | Local React state only (`useState` / `useEffect` / `useCallback`) |
| Data fetching | Native `fetch` in `frontend/src/api.js` |
| UI kit | None — custom CSS |
| Lint | oxlint |

### Backend

| Concern | Choice |
|---------|--------|
| Framework | FastAPI **0.115** + Uvicorn |
| Config | `pydantic-settings` (`backend/config.py`) |
| Comfy HTTP | `httpx` |
| Comfy wait | `websockets` |
| DB | Motor (async MongoDB) + PyMongo GridFS |
| Images | Pillow (normalize upload → RGB PNG) |
| Prompt i18n | `deep-translator` (Google Translate) |

### Runtime / host

| Piece | Host |
|-------|------|
| SPA | **Vercel** |
| API | **Render** (`wan-studio-api`) |
| DB | **MongoDB** (typically Atlas) |
| Inference | **Local ComfyUI** (GPU), often exposed via **cloudflared** tunnel |

Python: **3.12.8** (`.python-version`, `runtime.txt`, Render `PYTHON_VERSION`).

---

## 5. Backend module map

Think of the API as five cooperating pieces:

```
main.py
  │
  ├─► prompt_fix.normalize_prompt()     # user text → English edit/motion prompt
  ├─► Pillow                             # upload → RGB PNG bytes
  ├─► ComfyClient                        # talk to ComfyUI
  │     └─► workflows_wan                # build graph JSON
  │     └─► scrub                        # wipe local wan_* files + history
  └─► db                                 # GridFS + generations collection
```

| Module | Path | Job |
|--------|------|-----|
| Routes / lifecycle | `backend/main.py` | CORS, health, generate, library, media stream; connect DB on startup; optional scrub on boot |
| Settings | `backend/config.py` | All env knobs: Mongo, Comfy URL, Flux/Wan filenames, sizes, scrub flags |
| Persistence | `backend/db.py` | `connect` / `store_media` / list / get / patch / delete / stream |
| Comfy driver | `backend/comfy_client.py` | `/upload/image` → `/prompt` → WS wait → `/history` → `/view` → scrub |
| Graphs | `backend/workflows_wan.py` | `build_i2i_prompt` (Flux), `build_i2v_prompt` (Wan dual KSampler) |
| Prompt pipeline | `backend/prompt_fix.py` | Cleanup + translate + frame as edit vs motion |
| Disk hygiene | `backend/scrub.py` | Zero-overwrite + unlink `wan_*` under Comfy input/output/temp |

### Optional ComfyUI custom nodes

`comfy_nodes/wan_studio_i2i/` ships `Wan22ImageToImageLatent`. **Current production workflows in `workflows_wan.py` use Flux for stills and Wan for video** — they do not depend on this custom node. Treat it as an optional/experimental install into ComfyUI’s `custom_nodes`.

---

## 6. API surface

Base path: `/api/*`. All JSON/media responses use `Cache-Control: no-store` (and related no-cache headers).

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/health` | Mongo + ComfyUI reachability; model config snapshot |
| `POST` | `/api/scrub` | Manual wipe of local `wan_*` ComfyUI files (+ optional history clear) |
| `POST` | `/api/generate` | Multipart generate (`mode`, `prompt`, `image`, optional `negative` / `seed`) |
| `GET` | `/api/generations` | List recent jobs (`limit`, max 100) |
| `GET` | `/api/generations/{id}` | One job + `media_url` |
| `PATCH` | `/api/generations/{id}` | Update `prompt` and/or `meta` |
| `DELETE` | `/api/generations/{id}` | Delete Mongo doc + GridFS file |
| `GET` | `/api/media/{id}` | Stream binary (image/video) from GridFS |

**Auth:** none. If the API is reachable, routes are open. Protect via network / CORS / private deploy.

**CORS:** `CORS_ORIGINS` (`*` or comma-separated list).

**Static SPA (optional):** if `SERVE_FRONTEND=true` and `frontend/dist` exists, FastAPI mounts the built SPA (local all-in-one). On Render, `SERVE_FRONTEND=false`; Vercel serves the UI.

---

## 7. Data model (MongoDB)

**Database:** `MONGODB_DB` (default `wan_studio`).

### Collection: `generations`

| Field | Type | Meaning |
|-------|------|---------|
| `_id` | ObjectId | Exposed as string `id` in API |
| `kind` | `"img"` \| `"vid"` | Generation mode |
| `prompt` | string | Original user prompt |
| `model` | string | Flux unet name, or Wan high+low unet names |
| `content_type` | string | e.g. `image/png`, `video/mp4` |
| `filename` | string | e.g. `wan_img_….png` |
| `gridfs_id` | ObjectId | Pointer into GridFS bucket |
| `size_bytes` | int | Payload size |
| `meta` | object | `negative`, `seed`, `mode`, `prompt_original`, `prompt_english`, … |
| `created_at` | datetime | Insert time |
| `updated_at` | datetime | Set on PATCH |

### GridFS bucket: `media`

Stores **bytes only**. Upload metadata typically includes `content_type`, `kind`, `prompt`, `model`, `created_at`.

There are no SQL migrations; schema is document-oriented and defined in `backend/db.py`.

---

## 8. Generation pipeline (end-to-end)

This is the core architecture path:

```
Browser
  FormData: mode, prompt, image [, negative, seed]
       │
       ▼
POST /api/generate
       │
       ├─1─ normalize_prompt(mode, prompt)
       │      • cleanup typos / Hinglish-ish text
       │      • translate → English (deep-translator; fail-soft)
       │      • frame as edit (img) or motion (vid)
       │
       ├─2─ Pillow: decode upload → RGB → PNG bytes
       │
       ├─3─ ComfyClient.generate_image | generate_video
       │      a. upload as wan_in_*.png → ComfyUI /upload/image
       │      b. build workflow JSON (workflows_wan)
       │      c. POST /prompt  (queue on Comfy)
       │      d. WS /ws?clientId=…  wait until done
       │      e. GET /history/{prompt_id} → output filenames
       │      f. GET /view → raw image/video bytes (in memory)
       │      g. scrub: delete history + wipe wan_* disk files
       │
       ├─4─ db.store_media → GridFS + generations document
       │
       └─5─ JSON response { id, media_url, kind, prompt_english, … }
```

### Representative generate response

```json
{
  "id": "<ObjectId hex>",
  "kind": "img",
  "prompt": "…",
  "prompt_english": "…",
  "model": "flux1-dev-fp8.safetensors",
  "content_type": "image/png",
  "size_bytes": 123456,
  "created_at": "…",
  "media_url": "/api/media/<id>",
  "local_residue": false
}
```

### Frontend follow-on UX

After a successful **img** generation, the UI can fetch the media as a `File` and reload it into the drop zone for **iterative edits** (`App.jsx` + `fetchMediaAsFile` in `api.js`).

---

## 9. ComfyUI workflow architecture

Graphs are built in Python as node-id → node-config dicts, then submitted to ComfyUI’s `/prompt` API.

### Image (`build_i2i_prompt`) — Flux Dev img2img

Conceptual chain:

```
UNETLoader + DualCLIPLoader + VAELoader
  → FluxGuidance
  → LoadImage → ImageScale → VAEEncode
  → ModelSamplingFlux → KSampler (denoise ~0.28–0.55)
  → VAEDecode → SaveImage (prefix flux_i2i / wan_*)
```

Tunables via env: `FLUX_*`, `IMAGE_WIDTH/HEIGHT`, `IMAGE_DENOISE`, `SAMPLER_STEPS`.

### Video (`build_i2v_prompt`) — Wan 2.2 I2V 14B

Conceptual chain:

```
UNET high-noise + UNET low-noise + CLIP (UMT5) + Wan VAE
  → WanImageToVideo (start frame → latent video)
  → KSamplerAdvanced (high) → KSamplerAdvanced (low)
  → VAEDecode → CreateVideo → SaveVideo (prefix wan_i2v14)
```

Tunables via env: `WAN_*`, `VIDEO_WIDTH/HEIGHT/LENGTH/FPS/STEPS/CFG`.

### ComfyUI HTTP/WS contract (API → Comfy)

| Call | Use |
|------|-----|
| `GET /system_stats` | Health ping |
| `POST /upload/image` | Push start frame |
| `POST /prompt` | Enqueue workflow |
| `WS /ws?clientId=` | Wait for completion events |
| `GET /history/{id}` | Resolve output paths |
| `GET /view?...` | Download output bytes |

Timeout: `COMFYUI_TIMEOUT_SEC` (default 1200s).

---

## 10. Zero-residue / privacy architecture

Outputs are **not** meant to remain on the GPU machine’s disk after the job.

| Mechanism | Behavior |
|-----------|----------|
| `ZERO_RESIDUE` | After fetch, wipe matching artifacts under Comfy `input` / `output` / `temp` |
| `SCRUB_PASSES` | Overwrite passes before unlink |
| `SCRUB_CLEAR_ALL_HISTORY` | Prefer clearing Comfy history broadly vs prompt-id only |
| Prefix filter | Targets app-owned names (`wan_*`, related prefixes) |
| Startup scrub | If `COMFYUI_DIR` set, wipe on API lifespan start |
| `POST /api/scrub` | Manual operator wipe |
| Response headers | `no-store` so browsers/CDNs don’t cache media responses |
| Uvicorn | `--no-access-log` on Render to avoid request logs on disk |

**Important:** media still exists in **MongoDB GridFS**. “Zero residue” means **local ComfyUI disk**, not “no storage anywhere.”

**Security gap to be aware of:** no API keys, rate limits, or per-user isolation. Treat as a **trusted / private** deployment.

---

## 11. Frontend ↔ backend contract

| Concern | Detail |
|---------|--------|
| Protocol | HTTP(S) REST only |
| Dev | Vite proxies `/api` → `http://127.0.0.1:8000` |
| Prod | `VITE_API_URL` = Render API origin (e.g. `https://wan-studio-api.onrender.com`) |
| Generate | `multipart/form-data` |
| Patch | JSON `{ prompt?, meta? }` |
| Media | `<img>` / `<video src={mediaUrl}>` or blob download via `/api/media/{id}` |

Client wrappers live in `frontend/src/api.js`: `health`, `generate`, `listGenerations`, `getGeneration`, `updateGeneration`, `deleteGeneration`, `fetchMediaAsFile`, etc.

UI is one composition in `App.jsx`: mode tabs, drop zone, generate form, result panel, library list, health footer.

---

## 12. Deployment topology

### Production split

Canonical URLs are in [`PRODUCTION_URLS.md`](PRODUCTION_URLS.md):
- Frontend: https://frontend-six-chi-37.vercel.app
- API: https://wan-studio-api.onrender.com

```
Vercel  ──builds──►  frontend/dist  (static SPA)
                         │
                         │  VITE_API_URL
                         ▼
Render  ──runs──►  uvicorn backend.main:app
                         │
                         ├── MONGODB_URI ──► Atlas
                         └── COMFYUI_URL ──► tunnel ──► PC ComfyUI :8188
```

| Artifact | File | Notes |
|----------|------|-------|
| API service | `render.yaml` | Free plan web service, health `/api/health`, Python 3.12.8 |
| SPA | root `vercel.json` (+ `frontend/vercel.json`) | Install/build in `frontend/`, SPA rewrites to `index.html` |

### Local all-in-one

1. ComfyUI listening on `:8188`
2. `.env` with `MONGODB_URI`, `COMFYUI_URL=http://127.0.0.1:8188`, optional `COMFYUI_DIR`
3. `python run.py` (or uvicorn)
4. Optional: `SERVE_FRONTEND=true` after `npm run build` in `frontend/`
5. Or: Vite dev server with `/api` proxy

### Typical cloud + home-GPU ops

Render cannot reach `127.0.0.1` on your PC. Operators usually:

1. Run ComfyUI locally (`--listen 0.0.0.0 --port 8188`)
2. Run a **cloudflared** quick tunnel to `:8188`
3. Set Render env `COMFYUI_URL` to the tunnel HTTPS URL
4. Redeploy / update env when the tunnel URL changes

---

## 13. Configuration reference

Canonical template: `.env.example`. Typed loading: `backend/config.py`.

| Group | Keys | Role |
|-------|------|------|
| App | `APP_HOST`, `APP_PORT`, `CORS_ORIGINS`, `SERVE_FRONTEND` | Bind + CORS + static mount |
| DB | `MONGODB_URI`, `MONGODB_DB` | Persistence |
| Comfy | `COMFYUI_URL`, `COMFYUI_TIMEOUT_SEC`, `COMFYUI_DIR` | Inference endpoint + local scrub path |
| Scrub | `ZERO_RESIDUE`, `SCRUB_PASSES`, `SCRUB_CLEAR_ALL_HISTORY` | Disk hygiene |
| Flux | `FLUX_UNET`, `FLUX_CLIP_L`, `FLUX_T5`, `FLUX_VAE`, `FLUX_GUIDANCE`, `IMAGE_*`, `SAMPLER_STEPS` | Img graph |
| Wan | `WAN_UNET_HIGH`, `WAN_UNET_LOW`, `WAN_VAE`, `WAN_CLIP`, `WAN_SHIFT`, `VIDEO_*` | Vid graph |
| Frontend | `VITE_API_URL` | Prod API base |

Model **filenames** must match files present under ComfyUI’s model directories (`diffusion_models`, `clip`, `vae`, etc.).

---

## 14. Architectural style (how to think about it)

| Pattern | How it shows up here |
|---------|----------------------|
| **Orchestrator / sidecar** | FastAPI does not run models; it drives ComfyUI and stores results |
| **Synchronous request–response** | Long-lived HTTP generate; no Celery/Redis job queue in-app |
| **External GPU worker** | ComfyUI is the worker; tunnel makes it reachable from cloud API |
| **Blob store via GridFS** | Media co-located with Mongo metadata (no S3) |
| **SPA + BFF-ish API** | Thin REST API tailored to one studio UI |
| **Defense-in-depth for disk** | Scrub + no-store + no access logs (not multi-tenant security) |

### What this is *not*

- Not a multi-user SaaS with auth/tenancy
- Not a YouTube automation / scheduler product (folder name `YtAuto` is historical/parent context only)
- Not an async job system with polling webhooks (browser waits on one HTTP call)
- Not a microservice mesh — two deployables (SPA + API) + DB + local Comfy

---

## 15. Quick mental model

> **React SPA** collects image + prompt → **FastAPI** normalizes prompt and submits a **ComfyUI workflow** → waits on **WebSocket** until GPU finishes → **pulls bytes into RAM** → **writes Mongo GridFS** → **wipes Comfy disk** → returns `media_url` → SPA displays from GridFS.

If you can follow that path through `App.jsx` → `api.js` → `main.py` → `comfy_client.py` / `workflows_wan.py` → `db.py` / `scrub.py`, you understand the architecture of this project.

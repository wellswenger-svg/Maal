# Wan Studio — Complete Technical Architecture Report

**Product name:** Wan Studio  
**Repository root:** `d:\YtAuto\contrnt`  
**Report type:** Full developer architecture extraction (no summarization)  
**ComfyUI install inspected:** `E:\Comfy-Desktop\ComfyUI-Installs\Khelukhiladi\ComfyUI`  
**Shared weights path:** `E:\Comfy-Desktop\ComfyUI-Shared\models` (via `extra_model_paths.yaml`)  
**GPU inspected:** NVIDIA GeForce RTX 5060 Ti  
**Torch / CUDA inspected (ComfyUI venv):** `torch 2.10.0+cu130`, CUDA `13.0`

This report documents what exists in the **application repository** and what exists on the **local ComfyUI machine** that the app drives. Where something is installed on disk but **not wired into the app workflows**, that is stated explicitly.

---

# 1. Repository Structure

## 1.1 Complete folder tree (application repo)

```
contrnt/
├── .env.example
├── .gitignore
├── .python-version
├── runtime.txt
├── requirements.txt
├── render.yaml
├── vercel.json
├── run.py
├── TECHNICAL.md
├── reportarchitecture.md          ← this file
├── tokens&cmd                     ← local ops notes / secrets (gitignored)
├── deploy-render-service.json     ← local deploy note (gitignored)
│
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── comfy_client.py
│   ├── workflows_wan.py
│   ├── prompt_fix.py
│   └── scrub.py
│
├── frontend/
│   ├── .env.example
│   ├── .gitignore
│   ├── .oxlintrc.json
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   ├── README.md                  ← stock Vite template notes
│   ├── vercel.json
│   ├── vite.config.js
│   ├── public/
│   │   ├── favicon.svg
│   │   └── icons.svg
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── api.js
│       ├── index.css
│       └── assets/
│           ├── hero.png
│           ├── react.svg
│           └── vite.svg
│
└── comfy_nodes/
    └── wan_studio_i2i/
        └── __init__.py            ← optional ComfyUI custom node (not used by current API graphs)
```

There is **no** `docker-compose`, **no** Dockerfile, **no** Celery/Redis worker package, **no** SQL migrations folder, **no** React Router pages folder, **no** component library folder.

## 1.2 Purpose of every folder

| Folder | Purpose |
|--------|---------|
| `backend/` | FastAPI orchestration layer: HTTP API, Mongo/GridFS persistence, ComfyUI client, workflow JSON builders, prompt normalization, disk scrubbing |
| `frontend/` | React + Vite single-page studio UI (upload, generate, library CRUD) |
| `frontend/public/` | Static public assets (favicon, icons) |
| `frontend/src/` | Application source (entry, App, API client, CSS, unused Vite assets) |
| `frontend/src/assets/` | Bundled static images left from Vite template (`hero.png`, `react.svg`, `vite.svg`) — not part of generation pipelines |
| `comfy_nodes/` | Source of an optional ComfyUI custom node pack meant to be copied/symlinked into ComfyUI `custom_nodes/` |
| `comfy_nodes/wan_studio_i2i/` | Implements `Wan22ImageToImageLatent` for Wan 2.2 true img2img latent prep |
| Repo root | Entrypoint (`run.py`), Python deps, env templates, Render/Vercel deploy configs, docs |

## 1.3 Purpose of every important file

### Root

| File | Purpose |
|------|---------|
| `run.py` | Calls `backend.main.run()` → starts Uvicorn |
| `requirements.txt` | Python dependencies for the FastAPI app |
| `.env.example` | Canonical backend environment variable template |
| `.python-version` | Pins Python `3.12.8` (pyenv-style) |
| `runtime.txt` | Pins `python-3.12.8` (Render/Heroku-style) |
| `render.yaml` | Render Blueprint for `wan-studio-api` |
| `vercel.json` | Monorepo Vercel build: install/build `frontend/`, output `frontend/dist`, SPA rewrite |
| `TECHNICAL.md` | Earlier architecture overview |
| `reportarchitecture.md` | This complete report |
| `.gitignore` | Ignores `.env`, `tokens&cmd`, venv, `frontend/dist`, secrets deploy json, media binaries |

### Backend

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app, lifespan (Mongo connect + optional scrub), all HTTP routes, optional static SPA mount |
| `backend/config.py` | `pydantic-settings` Settings class; all env-backed knobs |
| `backend/db.py` | Motor Mongo client, GridFS bucket `media`, `generations` CRUD |
| `backend/comfy_client.py` | Upload → queue → WebSocket wait → fetch output → scrub; image/video generate methods |
| `backend/workflows_wan.py` | Builds ComfyUI API-format workflow dicts for Flux i2i and Wan i2v |
| `backend/prompt_fix.py` | Typo/Hinglish cleanup, Google Translate, edit/motion framing |
| `backend/scrub.py` | Secure zero-overwrite + unlink of ComfyUI input/output/temp artifacts |
| `backend/__init__.py` | Package marker |

### Frontend

| File | Purpose |
|------|---------|
| `frontend/index.html` | HTML shell; Google Fonts DM Sans + Instrument Serif; title Wan Studio |
| `frontend/src/main.jsx` | React 19 root mount of `<App />` |
| `frontend/src/App.jsx` | Entire UI: mode tabs, drop zone, generate form, result CRUD, library list, health footer |
| `frontend/src/api.js` | REST client (`generate`, library CRUD, media URL helpers, download, fetch-as-File) |
| `frontend/src/index.css` | All styling |
| `frontend/vite.config.js` | Vite + React plugin; proxies `/api` → `http://127.0.0.1:8000` |
| `frontend/package.json` | React/Vite/oxlint dependencies and scripts |
| `frontend/.env.example` | `VITE_API_URL=` |
| `frontend/vercel.json` | Framework vite + SPA rewrite |
| `frontend/.oxlintrc.json` | Lint config |

### Custom node (repo copy)

| File | Purpose |
|------|---------|
| `comfy_nodes/wan_studio_i2i/__init__.py` | Defines `Wan22ImageToImageLatent` node class + `NODE_CLASS_MAPPINGS` |

---

# 2. Backend

## 2.1 Framework

| Item | Value |
|------|-------|
| Framework | **FastAPI** `0.115.12` |
| ASGI server | **Uvicorn** `0.34.2` (`uvicorn[standard]`) |
| App object | `app = FastAPI(title="Wan Studio", version="1.0.0", lifespan=lifespan)` in `backend/main.py` |
| Settings | `pydantic-settings` `BaseSettings` in `backend/config.py` |
| Multipart | `python-multipart` |
| HTTP client to ComfyUI | `httpx` |
| WebSocket client to ComfyUI | `websockets` |
| Images | `Pillow` |
| DB driver | `motor` (async) + `pymongo` / GridFS |
| Translation | `deep-translator` |

Startup lifespan:

1. `await db.connect()` (Mongo ping)
2. If `ZERO_RESIDUE` and `COMFYUI_DIR` set → wipe `wan_*` artifacts under ComfyUI
3. On shutdown → `await db.close()`

CORS: `CORSMiddleware` from `CORS_ORIGINS` (`*` or comma-separated).

Access logs: disabled (`access_log=False`) to avoid request metadata on disk.

## 2.2 API routes

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| `GET` | `/api/health` | `health` | Ping Mongo + ComfyUI `/system_stats`; return model config snapshot |
| `POST` | `/api/scrub` | `scrub_now` | Manual wipe of local `wan_*` Comfy files + clear Comfy history |
| `POST` | `/api/generate` | `generate` | Multipart generation (`mode`, `prompt`, `image`, optional `negative`, `seed`) |
| `GET` | `/api/generations` | `generations` | List recent jobs (`limit`, capped at 100) |
| `GET` | `/api/generations/{gen_id}` | `generation_meta` | One job + `media_url` |
| `PATCH` | `/api/generations/{gen_id}` | `generation_update` | Update `prompt` and/or `meta` JSON |
| `DELETE` | `/api/generations/{gen_id}` | `generation_delete` | Delete Mongo doc + GridFS file |
| `GET` | `/api/media/{gen_id}` | `media` | Stream binary from GridFS |

Optional static SPA (only if `SERVE_FRONTEND=true` and `frontend/dist` exists):

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | Serve `index.html` |
| mount | `/assets` | Vite assets |
| `GET` | `/{full_path:path}` | SPA fallback |

All JSON/media responses attach:

```
Cache-Control: no-store, no-cache, must-revalidate, private
Pragma: no-cache
Expires: 0
```

### `POST /api/generate` form fields

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `mode` | yes | `"img"` \| `"vid"` | Selects Flux vs Wan pipeline |
| `prompt` | yes | string | Normalized before ComfyUI |
| `image` | yes | file | Converted to RGB PNG by Pillow |
| `negative` | no | string | Normalized with `frame=False` |
| `seed` | no | int | Random `0..2^32-1` if omitted |

### Generate response shape

```json
{
  "id": "<ObjectId hex>",
  "kind": "img|vid",
  "prompt": "<original user prompt>",
  "prompt_english": "<normalized English used by Comfy>",
  "model": "<flux unet OR high+low wan unets>",
  "content_type": "image/png|video/mp4|…",
  "size_bytes": 123,
  "created_at": "<iso>",
  "media_url": "/api/media/<id>",
  "local_residue": false
}
```

## 2.3 Worker flow

There is **no separate worker process**.

The FastAPI request handler **is** the worker:

```
HTTP request thread/async task (uvicorn)
  → normalize prompt
  → Pillow normalize image
  → ComfyClient.generate_image / generate_video
      → HTTP upload to ComfyUI
      → HTTP POST /prompt (ComfyUI internal queue)
      → WebSocket wait until executing node=null
      → HTTP GET /history + /view
      → scrub local files
  → Mongo GridFS store
  → HTTP JSON response
```

The browser HTTP call remains open for the entire generation (can be many minutes). Timeout budget is governed by:

- Uvicorn / reverse-proxy limits (Render / Cloudflare tunnel)
- `COMFYUI_TIMEOUT_SEC` (default **1200**) inside `ComfyClient._wait_ws`

## 2.4 Queue

| Layer | Queue? | Detail |
|-------|--------|--------|
| App (FastAPI) | **No** | No Celery, RQ, Redis, Bull, ARQ, Dramatiq |
| ComfyUI | **Yes (external)** | ComfyUI’s own `/prompt` queue; app waits via WebSocket `client_id` |
| App concurrency | Implicit | Multiple simultaneous `/api/generate` calls each enqueue separate Comfy prompts; GPU serializes them inside ComfyUI |

App queue body sent to ComfyUI:

```json
{
  "prompt": { "<node_id>": { "class_type": "...", "inputs": {...} }, ... },
  "client_id": "<uuid hex>"
}
```

Completion detection (`comfy_client._wait_ws`):

- Listen on `ws[s]://<host>/ws?clientId=<id>`
- On `execution_error` for matching `prompt_id` → raise
- On `executing` with matching `prompt_id` and `node == null` → done

## 2.5 Database

| Item | Value |
|------|-------|
| Engine | **MongoDB** |
| Driver | Motor `AsyncIOMotorClient` |
| Database name | `MONGODB_DB` default `wan_studio` |
| Collection | `generations` |
| Binary store | GridFS bucket name **`media`** |

### `generations` document fields

| Field | Type | Meaning |
|-------|------|---------|
| `_id` | ObjectId | Serialized as `id` string in API |
| `kind` | `"img"` \| `"vid"` | Mode |
| `prompt` | string | Original user prompt (not necessarily English) |
| `model` | string | For img: Flux UNET filename; for vid: `high+low` joined by `+` |
| `content_type` | string | MIME of stored media |
| `filename` | string | `wan_img_<uuid>.png` or `wan_vid_<uuid>.mp4` etc. |
| `gridfs_id` | ObjectId | GridFS file id |
| `size_bytes` | int | Byte length |
| `meta` | object | See below |
| `created_at` | datetime UTC | Insert time |
| `updated_at` | datetime UTC | Only on PATCH |

### `meta` object written on generate

```python
{
  "negative": <str|None>,
  "seed": <int|None>,
  "mode": "img"|"vid",
  "prompt_original": <str>,
  "prompt_english": <str>,
}
```

### GridFS upload metadata

```python
{
  "content_type": ...,
  "kind": ...,
  "prompt": ...,
  "model": ...,
  "created_at": <iso string>,
}
```

No indexes are created in code. No migrations. No user collection. No jobs collection separate from `generations`.

## 2.6 Storage

| What | Where |
|------|-------|
| Final images/videos | **MongoDB GridFS only** |
| Generation metadata | MongoDB `generations` |
| Temporary input during job | ComfyUI `input/` as `wan_in_<uuid>.png` then scrubbed |
| Temporary outputs during job | ComfyUI `output/` (`flux_i2i_*`, `wan_i2v14_*`) then scrubbed |
| App local disk media | Intentionally **not** kept (`ZERO_RESIDUE`) |

Scrub targets (`backend/scrub.py`):

- Prefixes: `wan_in_`, `wan_i2i`, `wan_i2v`, `ComfyUI_temp`
- Also any filename starting with `wan_` or containing `wan_i`
- Folders: `input/`, `output/`, `temp/` under ComfyUI root
- Method: overwrite with null bytes (`SCRUB_PASSES` times) then `unlink`

## 2.7 Authentication

**None.**

- No JWT
- No API keys
- No sessions / cookies
- No OAuth
- No per-user ownership on `generations`
- No rate limiting middleware

Security posture is:

- Network exposure control (private deploy / CORS)
- Disk residue wiping
- `Cache-Control: no-store`
- Disabled access logs

If the Render URL is public, anyone who can reach it can generate and read/delete all library items.

## 2.8 Job lifecycle

Exact lifecycle of one generation job:

```
1. Client POST /api/generate (multipart)
2. Validate prompt non-empty
3. normalize_prompt(prompt, mode) → english
4. If negative provided → normalize_prompt(negative, frame=False)
5. Pillow: open upload → RGB → PNG bytes
6. ComfyClient.health() must be true else HTTP 503
7. Branch:
     img → generate_image(...)
     vid → generate_video(...)
8. Inside ComfyClient:
     a. _prep_edit_image: aspect-fit resize to max box (LANCZOS), PNG
     b. _upload_image → wan_in_<uuid>.png on Comfy input/
     c. build_i2i_prompt OR build_i2v_prompt
     d. _queue → prompt_id
     e. _wait_ws until done or timeout
     f. _history → outputs
     g. pick last media from prefer order
          img prefer: images, gifs, videos
          vid prefer: videos, gifs, images
     h. _view → bytes in RAM
     i. _full_scrub (history delete + wipe listed files + wipe input + wipe wan_* leftovers)
9. db.store_media → GridFS + generations insert
10. Optional extra wipe_our_artifacts if ZERO_RESIDUE
11. Return JSON with media_url
12. On exception: scrub + HTTP 502/500; image_bytes deleted; gc.collect()
```

States are **not** persisted as `queued|running|failed|done`. Either the HTTP request succeeds with a stored record, or it fails with an error and typically no generation doc (failure before `store_media`).

## 2.9 File upload flow

### Browser → API

1. User drops/selects image in `App.jsx` → `File` in React state + object URL preview
2. On submit, `api.generate` builds `FormData`:
   - `mode`
   - `prompt`
   - `image` (File)
   - optional `negative`, `seed`
3. `POST /api/generate`

### API → normalize image

`_read_image_bytes` in `main.py`:

1. `await file.read()`
2. Reject empty
3. `PIL.Image.open` → `convert("RGB")` → save PNG to `BytesIO`
4. Return PNG bytes

### API → ComfyUI

`_prep_edit_image` in `comfy_client.py`:

1. Open PNG/RGB
2. `fit_dims(src_w, src_h, max_w, max_h)` — preserve aspect, snap to multiple of 16, never upscale above source (`scale = min(max/src, 1.0)`)
3. LANCZOS resize if needed
4. Re-encode PNG

`_upload_image`:

1. Name `wan_in_<uuid>.png`
2. `POST {COMFYUI_URL}/upload/image` with `overwrite=true`, `type=input`
3. Return Comfy filename for `LoadImage` node

After generation success/failure scrub removes that input file when `ZERO_RESIDUE=true`.

---

# 3. Frontend

## 3.1 Framework

| Item | Value |
|------|-------|
| UI library | **React** `^19.2.8` |
| DOM renderer | `react-dom` `^19.2.8` |
| Build tool | **Vite** `^8.2.0` |
| React plugin | `@vitejs/plugin-react` `^6.0.4` |
| Router | **None** |
| Global state library | **None** (local `useState` / `useCallback` / `useEffect` / `useRef`) |
| UI component library | **None** |
| CSS | Single file `index.css` |
| Lint | `oxlint` |
| Fonts | Google Fonts: **DM Sans**, **Instrument Serif** |
| Dev server | port `5173`, proxy `/api` → `http://127.0.0.1:8000` |
| Prod API base | `import.meta.env.VITE_API_URL` |

## 3.2 Pages

There is **one page** — the entire SPA is `App.jsx`.

Conceptual sections on that page (not separate routes):

1. Brand header (`Wan` / `img · vid · cloud store`)
2. Generation panel (mode + drop zone + prompt + submit)
3. Status line
4. Result stage (image/video + CRUD actions)
5. Library / history list
6. Health footer

## 3.3 Components

There are **no separate React component files**. Everything is inline in `App.jsx`.

Logical UI units inside `App`:

| Unit | Implementation |
|------|----------------|
| Mode tabs | Two buttons `img` / `vid` (`role="tablist"`) |
| Drop zone | `<label className="drop">` with drag/drop + hidden file input |
| Prompt field | `<textarea>` |
| Generate button | Submit button with spinner when `loading` |
| Status | `<p role="status">` |
| Result stage | `<video>` or clickable `<img>` |
| Result CRUD | download / use as input / edit prompt / save / delete |
| Library | `<ul className="library">` of thumbs + download + delete |
| Health footer | mongo/comfy/zero-residue text |

API module functions (`api.js`) used as the data layer:

- `getHealth`
- `listGenerations`
- `getGeneration`
- `updateGeneration`
- `deleteGeneration`
- `generate`
- `mediaUrl`
- `fetchMediaAsFile`
- `downloadGeneration`

## 3.4 Upload flow (frontend)

```
User selects/drops image
  → pickFile(f)
  → validate f.type starts with "image/"
  → setFile(f)
  → revoke old object URL
  → setPreviewUrl(URL.createObjectURL(f))
  → preview <img> shown in drop zone
```

Clear path: `clearInput()` clears file, revokes URL, resets `<input type=file>`.

Library → editor path:

```
Click library image OR "use as input"
  → fetchMediaAsFile(item)  // GET /api/media/{id} → Blob → File
  → pickFile(file)
  → setMode("img")
  → clear prompt
  → scroll to top, focus prompt
```

Videos cannot be used as input (error status).

## 3.5 Generate flow (frontend)

```
onSubmit
  → require file + non-empty prompt
  → setLoading(true)
  → status: "Sending to Flux Dev…" OR "Sending to Wan 2.2 I2V 14B…"
  → generate({ mode, prompt, file })
  → setResult(data)
  → refreshLibrary()
  → if result is image:
        fetchMediaAsFile(data) → pickFile(next)  // iterative edit loop
        clear prompt
     else:
        clearInput()
  → setLoading(false)
```

Notes:

- Frontend does **not** send `negative` or `seed` in the default UI (API supports them; UI does not expose fields).
- No progress percentage; only a spinner and status text.
- No client-side WebSocket to the API.

## 3.6 History

“History” in the UI is the section titled **`library`**.

Behavior:

- On mount: `listGenerations(30)`
- Manual refresh button
- After generate / save prompt / delete → refresh again
- Each row shows kind badge, prompt text, thumbnail (`<img>` or muted `<video>`)
- Click image → load into editor (`useAsInput`)
- Click video → set as result for viewing only
- Per-row download and delete

There is **no** separate history pagination UI, filtering, search, or infinite scroll beyond `limit=30` default (API max 100).

## 3.7 Gallery

There is **no distinct Gallery page/component**.

The **library list** is the gallery:

- Chronological newest-first from Mongo
- Serves as both history and selectable media browser
- Media always loaded from `/api/media/{id}` (GridFS), never from local ComfyUI

---

# 4. ComfyUI Integration

The application does **not** load `.json` workflow files from disk. Workflows are **built in Python** as ComfyUI API-format dicts in `backend/workflows_wan.py` and POSTed to `/prompt`.

There are **exactly two** production workflows:

1. **IMG** — `build_i2i_prompt` — Flux Dev img2img
2. **VID** — `build_i2v_prompt` — Wan 2.2 I2V 14B dual-stage

## 4.1 Workflow A — Flux Dev Image Edit (`build_i2i_prompt`)

### Complete node graph (every node)

| Node ID | class_type | Inputs | Role |
|---------|------------|--------|------|
| `1` | `UNETLoader` | `unet_name=flux_unet`, `weight_dtype=default` | Load Flux Dev UNET |
| `2` | `DualCLIPLoader` | `clip_name1=flux_clip_l`, `clip_name2=flux_t5`, `type=flux`, `device=default` | Load CLIP-L + T5XXL |
| `3` | `VAELoader` | `vae_name=flux_vae` | Load Flux AE VAE |
| `4` | `CLIPTextEncode` | `text=pos`, `clip=[2,0]` | Positive conditioning |
| `5` | `CLIPTextEncode` | `text=neg`, `clip=[2,0]` | Negative conditioning |
| `6` | `FluxGuidance` | `conditioning=[4,0]`, `guidance=<float>` | Flux guidance scale on positive |
| `7` | `LoadImage` | `image=image_name` | Load uploaded start image |
| `8` | `ImageScale` | `image=[7,0]`, `upscale_method=lanczos`, `width`, `height`, `crop=disabled` | Resize to target |
| `9` | `VAEEncode` | `pixels=[8,0]`, `vae=[3,0]` | Image → latent |
| `10` | `ModelSamplingFlux` | `model=[1,0]`, `max_shift=1.15`, `base_shift=0.5`, `width`, `height` | Flux sampling schedule shifts |
| `11` | `KSampler` | see parameters section | Denoise latent |
| `12` | `VAEDecode` | `samples=[11,0]`, `vae=[3,0]` | Latent → pixels |
| `13` | `SaveImage` | `images=[12,0]`, `filename_prefix=flux_i2i` | Write output file |

### Positive prompt construction inside workflow builder

Before nodes run, Python wraps the already-normalized English prompt:

```
Photorealistic photograph. This is an image edit of the provided photo.
Preserve identity, face, body, pose, camera angle, framing, lighting,
and background exactly. Do not invent a new person or scene.
Only apply this requested change: {edit}
```

Denoise is clamped in builder:

```
strength = max(0.28, min(0.55, float(denoise)))
```

### Pipeline chain (requested style)

```
Input image (uploaded wan_in_*.png)
↓
LoadImage (node 7)
↓
ImageScale lanczos → target W×H, crop disabled (node 8)
↓
VAEEncode via ae.safetensors (node 9)
↓
UNETLoader flux1-dev-fp8 (node 1)
↓
ModelSamplingFlux max_shift=1.15 base_shift=0.5 (node 10)
↓
DualCLIPLoader clip_l + t5xxl_fp8 (node 2)
↓
CLIPTextEncode positive (node 4) → FluxGuidance (node 6)
CLIPTextEncode negative (node 5)
↓
KSampler
  model=ModelSamplingFlux
  latent=VAEEncode
  positive=FluxGuidance
  negative=CLIPTextEncode(neg)
  sampler=euler
  scheduler=simple
  cfg=1.0
  steps=<SAMPLER_STEPS>
  denoise=<clamped IMAGE_DENOISE>
  seed=<seed>
↓
VAEDecode (node 12)
↓
SaveImage prefix flux_i2i (node 13)
↓
Output image bytes fetched via /view then scrubbed from disk
```

### Every model loader in this workflow

- `UNETLoader` → Flux UNET
- `DualCLIPLoader` → CLIP-L + T5
- `VAELoader` → Flux AE

### Every sampler / scheduler

- Sampler: **`euler`**
- Scheduler: **`simple`**
- CFG: **`1.0`** (Flux uses `FluxGuidance` instead of classic CFG)
- Guidance node: **`FluxGuidance`** with env `FLUX_GUIDANCE`

### Every latent operation

- `VAEEncode` (pixels → latent)
- `KSampler` denoise on latent
- `VAEDecode` (latent → pixels)
- `ModelSamplingFlux` (sampling parameterization on model, not a latent tensor op but required for Flux sampling)

### Every image operation

- `LoadImage`
- `ImageScale` (`lanczos`, `crop=disabled`)
- `SaveImage`

**Not present in this workflow:** mask, inpaint, IPAdapter, PuLID, ControlNet, LoRA, upscaler, face restore, segmentation, compositing.

---

## 4.2 Workflow B — Wan 2.2 I2V 14B (`build_i2v_prompt`)

### Complete node graph (every node)

| Node ID | class_type | Inputs | Role |
|---------|------------|--------|------|
| `1` | `UNETLoader` | `unet_name=unet_high`, `weight_dtype=default` | High-noise expert UNET |
| `2` | `UNETLoader` | `unet_name=unet_low`, `weight_dtype=default` | Low-noise expert UNET |
| `3` | `CLIPLoader` | `clip_name=clip`, `type=wan`, `device=default` | UMT5 XXL text encoder |
| `4` | `VAELoader` | `vae_name=vae` | Wan VAE |
| `5` | `CLIPTextEncode` | `text=pos`, `clip=[3,0]` | Positive |
| `6` | `CLIPTextEncode` | `text=neg`, `clip=[3,0]` | Negative |
| `7` | `LoadImage` | `image=image_name` | Start frame |
| `8` | `ModelSamplingSD3` | `model=[1,0]`, `shift=<wan_shift>` | Shift for high-noise model |
| `9` | `ModelSamplingSD3` | `model=[2,0]`, `shift=<wan_shift>` | Shift for low-noise model |
| `10` | `WanImageToVideo` | positive, negative, vae, width, height, length, batch_size=1, start_image | Build conditioned video latent from start image |
| `11` | `KSamplerAdvanced` | high-noise stage | Steps `0 → split`, add_noise enable, return leftover noise |
| `12` | `KSamplerAdvanced` | low-noise stage | Steps `split → 10000`, add_noise disable |
| `13` | `VAEDecode` | `samples=[12,0]`, `vae=[4,0]` | Decode frame latents |
| `14` | `CreateVideo` | `images=[13,0]`, `fps` | Pack frames to video tensor/container |
| `15` | `SaveVideo` | `video=[14,0]`, `filename_prefix=wan_i2v14`, `format=auto`, `codec=auto` | Write video file |

### Length snapping

```
length = max(5, int(length))
if (length - 1) % 4 != 0:
    length = ((length - 1) // 4) * 4 + 1
```

### Step split

```
total_steps = max(8, int(steps))
split = max(1, total_steps // 2)
```

Default 20 steps → split at 10: high-noise does 0–10, low-noise does 10–end.

### Pipeline chain (requested style)

```
Input image (uploaded wan_in_*.png)
↓
LoadImage (node 7)
↓
CLIPLoader umt5_xxl (node 3)
↓
CLIPTextEncode positive (node 5)
CLIPTextEncode negative (node 6)
↓
VAELoader wan_2.1_vae (node 4)
↓
WanImageToVideo (node 10)
  - encodes start_image through VAE
  - builds length-frame latent video
  - injects start-frame conditioning / identity lock
  - outputs: positive cond, negative cond, latent_image
↓
UNETLoader high-noise (node 1) → ModelSamplingSD3 shift (node 8)
↓
KSamplerAdvanced stage 1 (node 11)
  add_noise=enable
  noise_seed=seed
  start_at_step=0
  end_at_step=split
  return_with_leftover_noise=enable
  sampler=euler
  scheduler=simple
  cfg=<VIDEO_CFG>
↓
UNETLoader low-noise (node 2) → ModelSamplingSD3 shift (node 9)
↓
KSamplerAdvanced stage 2 (node 12)
  add_noise=disable
  noise_seed=0
  start_at_step=split
  end_at_step=10000
  return_with_leftover_noise=disable
  sampler=euler
  scheduler=simple
  cfg=<VIDEO_CFG>
  latent_image=stage1 output
↓
VAEDecode (node 13)
↓
CreateVideo fps=<VIDEO_FPS> (node 14)
↓
SaveVideo prefix wan_i2v14 format=auto codec=auto (node 15)
↓
Output video bytes fetched via /view then scrubbed
```

### Every model loader in this workflow

- `UNETLoader` ×2 (high + low)
- `CLIPLoader` (Wan / UMT5)
- `VAELoader` (Wan VAE)

### Every sampler / scheduler

- Both stages: sampler **`euler`**, scheduler **`simple`**
- CFG on both stages: **`VIDEO_CFG`** (default 3.5)
- Shift via `ModelSamplingSD3`: **`WAN_SHIFT`** (default 5.0)

### Every latent operation

- `WanImageToVideo` (image → conditioned video latent + cond)
- `KSamplerAdvanced` ×2 (partial denoising stages)
- `VAEDecode`

### Every image / video operation

- `LoadImage`
- `CreateVideo`
- `SaveVideo`

**Not present:** RIFE/FILM interpolation nodes, latent upscale, spatial upscaler, ControlNet, LoRA loaders, audio, camera control nodes, face lock nodes.

---

## 4.3 ComfyUI HTTP / WS endpoints used by the app

| Endpoint | Method | Used for |
|----------|--------|----------|
| `/system_stats` | GET | Health + optional argv-based root detection |
| `/upload/image` | POST | Upload start frame |
| `/prompt` | POST | Enqueue workflow |
| `/ws?clientId=` | WS | Wait for completion / errors |
| `/history/{prompt_id}` | GET | Resolve output filenames |
| `/history` | POST | `{delete:[id]}` and/or `{clear:true}` scrub |
| `/view?filename&subfolder&type` | GET | Download output bytes |

## 4.4 Custom node referenced by app workflows

**None of the production workflow nodes are custom-pack nodes.**

All class types used (`UNETLoader`, `DualCLIPLoader`, `VAELoader`, `CLIPTextEncode`, `FluxGuidance`, `LoadImage`, `ImageScale`, `VAEEncode`, `ModelSamplingFlux`, `KSampler`, `VAEDecode`, `SaveImage`, `CLIPLoader`, `ModelSamplingSD3`, `WanImageToVideo`, `KSamplerAdvanced`, `CreateVideo`, `SaveVideo`) are **ComfyUI core / built-in** nodes (Wan/Flux support as shipped with modern ComfyUI).

The repo custom node `Wan22ImageToImageLatent` is **not referenced** by `workflows_wan.py`.

---

# 5. Models

## 5.1 Models used by the application workflows (wired in code / env)

### Flux Dev (IMG)

| Field | Value |
|-------|-------|
| Filename | `flux1-dev-fp8.safetensors` |
| Version / variant | Flux.1 **Dev**, **FP8** quantized weights |
| Typical repository | Black Forest Labs Flux.1-dev (fp8 community quant / Comfy-Org packaging) |
| Purpose | Img2img diffusion backbone for edits |
| Current settings | Loaded via `UNETLoader`; sampling via `ModelSamplingFlux` + `KSampler` |
| Env key | `FLUX_UNET` |

| Field | Value |
|-------|-------|
| Filename | `clip_l.safetensors` |
| Version | OpenAI CLIP-L text tower used by Flux |
| Repository | Standard Flux text encoder pack |
| Purpose | DualCLIP slot 1 |
| Env key | `FLUX_CLIP_L` |

| Field | Value |
|-------|-------|
| Filename | `t5xxl_fp8_e4m3fn.safetensors` |
| Version | T5-XXL FP8 e4m3fn |
| Repository | Standard Flux text encoder pack |
| Purpose | DualCLIP slot 2 (long prompt encoder) |
| Env key | `FLUX_T5` |

| Field | Value |
|-------|-------|
| Filename | `ae.safetensors` |
| Version | Flux Autoencoder (AE) |
| Repository | Black Forest Labs Flux VAE |
| Purpose | Encode/decode latents for Flux |
| Env key | `FLUX_VAE` |

### Wan 2.2 I2V (VID)

| Field | Value |
|-------|-------|
| Filename | `wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors` |
| Version | Wan **2.2** I2V **14B** high-noise expert, FP8 scaled |
| Repository | Wan-AI / Comfy-Org Wan2.2 I2V-A14B packaging |
| Purpose | First denoising stage (high noise) |
| Env key | `WAN_UNET_HIGH` |

| Field | Value |
|-------|-------|
| Filename | `wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors` |
| Version | Wan **2.2** I2V **14B** low-noise expert, FP8 scaled |
| Repository | Wan-AI / Comfy-Org Wan2.2 I2V-A14B packaging |
| Purpose | Second denoising stage (low noise / refinement) |
| Env key | `WAN_UNET_LOW` |

| Field | Value |
|-------|-------|
| Filename | `umt5_xxl_fp8_e4m3fn_scaled.safetensors` |
| Version | UMT5-XXL FP8 scaled |
| Repository | Wan text encoder pack |
| Purpose | Wan prompt encoding (`CLIPLoader` type=`wan`) |
| Env key | `WAN_CLIP` |

| Field | Value |
|-------|-------|
| Filename | `wan_2.1_vae.safetensors` |
| Version | **Wan 2.1 VAE** (note: not the `wan2.2_vae.safetensors` also present on disk) |
| Repository | Wan VAE pack |
| Purpose | Encode start frame / decode video latents |
| Env key | `WAN_VAE` |

## 5.2 Models present on the machine but NOT used by app workflows

These exist under `E:\Comfy-Desktop\ComfyUI-Shared\models` and/or the local install `models/` folder.

### Diffusion / checkpoints / GGUF (installed, unused by app)

| Filename | Approx size | Notes |
|----------|-------------|-------|
| `ltx-2.3-22b-dev-fp8.safetensors` | ~27.8 GB | LTX-2.3 22B checkpoint — unused |
| `wan2.1_t2v_1.3B_fp16.safetensors` | ~2.7 GB | Wan 2.1 T2V 1.3B — unused |
| `Wan2.2-T2V-A14B-HighNoise-Q5_K_M.gguf` | ~10.3 GB | Wan 2.2 T2V GGUF high — unused |
| `Wan2.2-T2V-A14B-LowNoise-Q5_K_M.gguf` | ~10.3 GB | Wan 2.2 T2V GGUF low — unused |
| `wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors` | ~13.6 GB | Wan 2.2 T2V high — unused |
| `wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors` | ~13.6 GB | Wan 2.2 T2V low fp8 — unused |
| `wan2.2_t2v_low_noise_14B_fp16.safetensors` | ~27.3 GB | Wan 2.2 T2V low fp16 — unused |
| `wan2.2_ti2v_5B_fp16.safetensors` | ~9.5 GB | Wan 2.2 TI2V 5B — unused (this is what `Wan22ImageToImageLatent` was aimed at) |
| `z_image_turbo_bf16.safetensors` | ~11.7 GB | Z-Image Turbo — unused |

### VAE (installed, alternate unused)

| Filename | Notes |
|----------|-------|
| `wan2.2_vae.safetensors` | Present (~1.3 GB) but app defaults to **`wan_2.1_vae.safetensors`** |

### Text encoders (installed, unused by app)

| Filename | Notes |
|----------|-------|
| `EVA02_CLIP_L_336_psz14_s6B.pt` | EVA-CLIP — unused by app |
| `gemma_3_12B_it_fp4_mixed.safetensors` | Gemma 3 12B — likely for LTX / other — unused by app |
| `qwen_3_4b.safetensors` | Qwen3-4B — unused by app |

### LoRA (installed, unused by app)

| Filename | Likely purpose |
|----------|----------------|
| `wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors` | 4-step distill LoRA for Wan I2V high |
| `wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors` | 4-step distill LoRA for Wan I2V low |
| `wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors` | T2V 4-step distill high |
| `wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors` | T2V 4-step distill low |
| `Wan21_T2V_14B_lightx2v_cfg_step_distill_lora_rank32.safetensors` | Wan 2.1 distill |
| `Instagirlv2.0_hinoise.safetensors` / `Instagirlv2.0_lownoise.safetensors` / `ifrgirl_wan22_low.safetensors` | Style LoRAs |
| `Lenovo.safetensors` | Unknown/custom style |
| `ltx_2.3_22b_distilled_1.1_lora_...` | LTX distill |
| `gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors` | LLM LoRA |

### Upscaler (installed, unused by app)

| Filename | Purpose |
|----------|---------|
| `4x-UltraSharp.pth` | 4× ESRGAN-family upscaler |
| `ltx-2.3-spatial-upscaler-x2-1.1.safetensors` | LTX latent/spatial upscaler |

### PuLID (installed on local Comfy models, unused by app)

| Filename | Version | Purpose | Used by app? |
|----------|---------|---------|--------------|
| `pulid_flux_v0.9.1.safetensors` | v0.9.1 | Flux identity preservation | **NO** |

### Face / ReActor stack (installed locally, unused by app)

| Filename / pack | Purpose | Used by app? |
|-----------------|---------|--------------|
| `inswapper_128.onnx` | Face swap | NO |
| InsightFace `antelopev2/*`, `buffalo_l/*` | Face analysis | NO |
| `codeformer-v0.1.0.pth` | Face restore | NO |
| `GFPGANv1.4.pth` | Face restore | NO |
| `detection_Resnet50_Final.pth`, `parsing_parsenet.pth`, `parsing_bisenet.pth` | Face detect/parse | NO |
| `face_yolov8m.pt` | YOLO face detect (Impact/Ultralytics) | NO |
| `vit-base-content-detector` | Content classifier | NO |

## 5.3 Categories requested by this report — status matrix

| Category | In app workflow? | On disk? | Details |
|----------|------------------|----------|---------|
| Flux Dev | **YES** | YES | `flux1-dev-fp8.safetensors` |
| Wan 2.2 | **YES (I2V 14B)** | YES (+ many unused Wan variants) | High/low I2V fp8 |
| IPAdapter | **NO** | Extension installed; **clip_vision models folder empty** | Pack `ComfyUI_IPAdapter_plus` present; no IPAdapter weights found in shared scan |
| PuLID | **NO** | YES `pulid_flux_v0.9.1.safetensors` + pack `ComfyUI_PuLID_Flux_ll` | Not wired |
| Florence2 | **NO** | **NOT FOUND** | No Florence2 weights/nodes observed |
| SAM2 | **NO** | `models/sams` folder exists but **empty** in scan | No SAM2 weights |
| GroundingDINO | **NO** | **NOT FOUND** | No weights observed |
| ControlNet | **NO** | Extension `comfyui_controlnet_aux` installed; **controlnet weights folder empty** | Preprocessors available, no ControlNet models |
| LoRA | **NO in app graph** | Many LoRAs on disk | Not loaded by `workflows_wan.py` |
| Upscaler | **NO in app graph** | `4x-UltraSharp.pth` present | Not used |
| VAE | **YES** | Flux `ae`, Wan `wan_2.1_vae` used; `wan2.2_vae` unused | |
| CLIP / text encoders | **YES** | `clip_l`, `t5xxl_fp8`, `umt5_xxl` used | Extra Gemma/Qwen/EVA unused |
| Anything else | — | LTX-2.3, Z-Image Turbo, GGUF Wan, face stack, content classifier | Unused by app |

---

# 6. Workflow Parameters

## 6.1 IMG — Flux Dev img2img (`build_i2i_prompt`)

| Parameter | Source | Current default | Effective behavior |
|-----------|--------|-----------------|-------------------|
| CFG | Hardcoded in workflow | **1.0** | Correct for Flux (guidance via `FluxGuidance`) |
| Steps | `SAMPLER_STEPS` / `settings.sampler_steps` | **28** | KSampler steps |
| Sampler | Hardcoded | **`euler`** | |
| Scheduler | Hardcoded | **`simple`** | |
| Denoise | `IMAGE_DENOISE` then clamped | **0.42** → clamp **[0.28, 0.55]** | Full-frame img2img strength |
| Resolution | `IMAGE_WIDTH` × `IMAGE_HEIGHT` as max box | **1024 × 1024** | Aspect-preserved fit; snap to multiple of 16; no upscale beyond source |
| FPS | N/A | N/A | Image workflow |
| Frame count | N/A | N/A | |
| Seed | Form field or random | `random.randint(0, 2**32-1)` if omitted | UI does not expose seed |
| Guidance | `FLUX_GUIDANCE` | **3.5** | `FluxGuidance` node |
| ModelSamplingFlux max_shift | Hardcoded | **1.15** | |
| ModelSamplingFlux base_shift | Hardcoded | **0.5** | |
| ImageScale method | Hardcoded | **lanczos** | |
| ImageScale crop | Hardcoded | **disabled** | |
| weight_dtype | Hardcoded | **default** | |
| Motion settings | N/A | N/A | |
| Context size | N/A | N/A | Not a context-window video model path |
| Overlap | N/A | N/A | No windowed video attention overlap configured |
| Noise | Via denoise + seed | Euler simple noise schedule | No extra noise injection nodes |
| Negative prompt | User or default | See §7 | |
| Positive wrapper | Hardcoded English edit framing | See §4.1 / §7 | |

## 6.2 VID — Wan 2.2 I2V 14B (`build_i2v_prompt`)

| Parameter | Source | Current default | Effective behavior |
|-----------|--------|-----------------|-------------------|
| CFG | `VIDEO_CFG` | **3.5** | Applied on **both** KSamplerAdvanced stages |
| Steps | `VIDEO_STEPS` | **20** | `total_steps`; split = `total_steps // 2` (10/10) |
| Sampler | Hardcoded both stages | **`euler`** | |
| Scheduler | Hardcoded both stages | **`simple`** | |
| Denoise | N/A as single float | Partial via advanced step ranges | Stage1: steps 0→split with leftover noise; Stage2: split→10000 |
| Resolution | `VIDEO_WIDTH` × `VIDEO_HEIGHT` max box | **640 × 640** | Aspect fit, snap 16 |
| FPS | `VIDEO_FPS` | **16** | `CreateVideo` |
| Frame count / length | `VIDEO_LENGTH` | **49** | Snapped so `(length-1) % 4 == 0`; min 5 |
| Seed | Form / random | Random 32-bit if omitted | Used as `noise_seed` on stage 1 only; stage 2 `noise_seed=0` with `add_noise=disable` |
| Guidance | N/A Flux-style | N/A | Uses CFG not FluxGuidance |
| Shift | `WAN_SHIFT` | **5.0** | `ModelSamplingSD3` on both UNETs |
| Motion settings | Prompt text only | Soft wrapper “Subtle natural motion…” if no motion verbs | No camera/trajectory nodes |
| Context size | Not configured in graph | Default WanImageToVideo / model internals | No explicit context/overlap nodes in app graph |
| Overlap | Not configured | N/A | |
| Noise | Stage1 `add_noise=enable`; Stage2 `add_noise=disable` | Dual-expert handoff | |
| batch_size | Hardcoded | **1** | |
| SaveVideo format/codec | Hardcoded | **auto** / **auto** | |
| Negative prompt | User or `DEFAULT_NEGATIVE_WAN` | Chinese + English quality negatives | |

### Dual-stage sampler detail

**Stage 1 (high noise)**

- `add_noise`: enable  
- `noise_seed`: seed  
- `start_at_step`: 0  
- `end_at_step`: split  
- `return_with_leftover_noise`: enable  

**Stage 2 (low noise)**

- `add_noise`: disable  
- `noise_seed`: 0  
- `start_at_step`: split  
- `end_at_step`: 10000  
- `return_with_leftover_noise`: disable  

---

# 7. Prompt Processing

All logic lives in `backend/prompt_norm.py`, invoked from `backend/main.py` before ComfyUI.

## 7.1 Pipeline order for positive prompts

```
raw user prompt
↓
_clean_spaces
↓
_fix_hinglish (regex phrase map)
↓
_fix_typos (token map)
↓
If non-Latin script OR Hinglish markers → GoogleTranslator(auto→en)
↓
_polish_english (heuristic; may translate again)
↓
_fix_typos + _fix_hinglish again
↓
Strip leftover romanized fillers: kar, dena, bhai, yaar, bas, nahi, haan
↓
Color pattern rewrite: "<noun> black" → "change <noun> to black" (first match)
↓
Strip orphan trailing "do|kar"
↓
Mode framing:
  img → _as_edit_instruction
  vid → _as_motion_instruction
↓
Returned as { original, cleaned, english }
↓
english sent to ComfyUI
↓
IMG ONLY: workflows_wan wraps again with photorealistic identity-preservation paragraph
```

## 7.2 Translation

- Library: **`deep-translator`** → `GoogleTranslator(source="auto", target="en")`
- Triggered when:
  - Unicode ranges for Devanagari and many other non-Latin scripts match, OR
  - Hinglish marker tokens present (`karo`, `banao`, `thoda`, `mujhe`, etc.)
- Failure mode: catch Exception → keep previous text (fail-soft)
- `_polish_english` may call translator again if text looks broken (many short tokens)

## 7.3 Prompt enhancement / automatic prompt engineering

What exists:

1. Typo dictionary (`pls`→`please`, `backround`→`background`, …)
2. Hinglish phrase dictionary (`hatao`→`remove`, `chehra`→`face`, …)
3. Edit framing for img:
   - Strips leading `generate/create/draw/paint/a photo of/...`
   - If not already starting with change/edit/replace/remove/add/turn/make → prefix `Edit this exact photo only: …`
4. Motion framing for vid:
   - Strips `generate/create/make a video of/animate`
   - If no motion keywords → `Subtle natural motion: {t}. Keep the same person and scene.`
5. Flux workflow adds a long hard-coded identity lock paragraph (§4.1)

What does **not** exist:

- No LLM prompt rewriter (no OpenAI/Claude/local LLM call in app)
- No Florence2 / Qwen-VL / LLaVA image captioning fed into the prompt
- No automatic subject detection tags
- No quality booster suffix catalogs beyond the Flux wrapper
- No regional prompt / attention weighting syntax builder
- No CLIP interrogation

## 7.4 Negative prompts

### API behavior

- Optional form field `negative`
- If provided: `normalize_prompt(negative, mode, frame=False)` — translate/clean only, **no** edit/motion wrapper
- If omitted: workflow defaults apply

### Default Flux negative (`DEFAULT_NEGATIVE_FLUX`)

```
blurry, low quality, jpeg artifacts, watermark, text, logo, deformed,
extra fingers, mutated hands, different person, identity change,
new subject, wrong face, cartoon, anime, oversaturated
```

### Default Wan negative (`DEFAULT_NEGATIVE_WAN`)

Chinese quality/motion negatives plus English:

```
色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，
最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，
画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走,
blurry, low quality, watermark, text, logo, deformed hands, extra limbs
```

### UI

Frontend **does not expose** a negative prompt field. Users always get defaults unless a custom client sends `negative`.

## 7.5 System prompts

There is no chat “system prompt” API.

Effective system-like text:

1. `_as_edit_instruction` / `_as_motion_instruction` wrappers
2. Flux positive prepend block in `build_i2i_prompt` (photorealistic / preserve identity…)

---

# 8. Image Editing Pipeline

## 8.1 Real end-to-end pipeline (what the code actually does)

```
User image file (any PIL-readable format)
↓
API Pillow convert → RGB PNG
↓
ComfyClient._prep_edit_image
  → aspect-fit inside max(IMAGE_WIDTH, IMAGE_HEIGHT) box
  → LANCZOS resize (never upscales beyond source)
  → PNG bytes
↓
Upload to ComfyUI input as wan_in_<uuid>.png
↓
LoadImage
↓
ImageScale (lanczos, crop disabled) to snapped W×H
↓
VAEEncode (Flux ae.safetensors)
↓
Full-latent img2img denoise with Flux Dev FP8
  (KSampler denoise ≈ 0.28–0.55, euler/simple, cfg 1.0, FluxGuidance 3.5)
↓
VAEDecode
↓
SaveImage (flux_i2i_*)
↓
API downloads bytes to RAM
↓
Scrub Comfy disk artifacts
↓
Store PNG (or returned type) in MongoDB GridFS
↓
Return /api/media/{id}
↓
Frontend may reload result as next input (iterative global edits)
```

## 8.2 What this pipeline is NOT

The following **do not happen**:

```
Image → Mask → Inpaint → Composite → Upscale   ❌ NOT IMPLEMENTED
Image → Florence2 caption → grounded edit      ❌ NOT IMPLEMENTED
Image → SAM2 segment → regional edit           ❌ NOT IMPLEMENTED
Image → GroundingDINO detect → box prompt      ❌ NOT IMPLEMENTED
Image → PuLID face embed → identity lock       ❌ NOT INSTALLED IN GRAPH
Image → IPAdapter reference                    ❌ NOT IN GRAPH
Image → ControlNet pose/depth                  ❌ NOT IN GRAPH
Image → FaceDetailer / ReActor                 ❌ NOT IN GRAPH
Image → UltimateSDUpscale / 4x-UltraSharp      ❌ NOT IN GRAPH
```

## 8.3 Practical editing behavior

Because editing is **global denoise img2img**:

- Low denoise → subtle changes, may ignore prompt
- High denoise (clamped max 0.55) → stronger edits but identity/background drift
- No mask means “change the shirt” can still alter face/lighting/background
- Identity preservation relies only on:
  - start latent
  - prompt text instructions
  - negative “different person / wrong face”
  - denoise cap

That is substantially weaker than ChatGPT Images / Krea-style edit stacks that combine understanding + masking + identity adapters.

---

# 9. Video Pipeline

## 9.1 Real end-to-end pipeline

```
User image
↓
API Pillow → RGB PNG
↓
_prep_edit_image to max VIDEO_WIDTH×VIDEO_HEIGHT (default 640×640 box)
↓
Upload wan_in_*.png
↓
LoadImage
↓
WanImageToVideo
  - VAE-encode start frame
  - allocate latent video length (default 49 frames)
  - bind start_image conditioning (identity/start-frame lock)
  - produce positive/negative conditioning + latent_image
↓
High-noise UNET (wan2.2_i2v_high_noise_14B_fp8_scaled)
  + ModelSamplingSD3(shift=5.0)
↓
KSamplerAdvanced stage 1 (euler/simple, cfg=3.5, steps 0→split, add_noise)
↓
Low-noise UNET (wan2.2_i2v_low_noise_14B_fp8_scaled)
  + ModelSamplingSD3(shift=5.0)
↓
KSamplerAdvanced stage 2 (euler/simple, cfg=3.5, steps split→end, no new noise)
↓
VAEDecode (wan_2.1_vae.safetensors)
↓
CreateVideo (fps=16)
↓
SaveVideo (auto format/codec, prefix wan_i2v14)
↓
API fetch bytes → scrub → GridFS → /api/media/{id}
```

## 9.2 Mapping to the requested abstract stages

| Requested stage | Present? | Implementation |
|-----------------|----------|----------------|
| Image | YES | Upload + LoadImage |
| Latent | YES | WanImageToVideo (+ VAE) |
| Motion conditioning | PARTIAL | Text prompt + WanImageToVideo start-frame conditioning only |
| Video model | YES | Dual Wan 2.2 I2V 14B experts |
| Interpolation | **NO** | No RIFE/FILM/frame interpolation nodes |
| Upscale | **NO** | Stays at ~640-class resolution |
| Encoding | YES | CreateVideo + SaveVideo (auto codec) |
| Output | YES | GridFS mp4/webm/gif depending on Comfy output |

## 9.3 Timing math (defaults)

- Frames: 49  
- FPS: 16  
- Duration ≈ 49/16 ≈ **3.06 seconds**  
- Steps: 20 total (10+10)  
- Resolution: up to 640×640 aspect-fit  

No camera path, no motion brush, no first-last frame pair (only start image), no audio.

---

# 10. Custom Nodes

## 10.1 Custom node shipped in this repository

### `Wan22ImageToImageLatent`

| Field | Value |
|-------|-------|
| Path | `comfy_nodes/wan_studio_i2i/__init__.py` |
| Also installed under ComfyUI | `.../custom_nodes/wan_studio_i2i` (present on machine) |
| Class | `Wan22ImageToImageLatent` |
| Category | `model/conditioning/wan` |
| Returns | `LATENT` |
| Why it was written | Wan22 `ImageToVideo` latent path keeps start-frame with `noise_mask=0` (no real denoise). This node encodes start image, applies `Wan22` `process_out`, omits noise_mask so KSampler can do true img2img on Wan22 TI2V-style latents (shape `[1,48,1,H/16,W/16]`). |
| Used by current app workflows? | **NO** — IMG path switched to Flux; this node is unused by `workflows_wan.py` |

Inputs:

- `vae` (VAE)
- `start_image` (IMAGE)
- `width` (INT, default 1024, step 32)
- `height` (INT, default 1024, step 32)
- `batch_size` (INT, default 1)

## 10.2 Custom node packs installed in ComfyUI (machine)

These are extensions/node packs under `custom_nodes/` (see §11 for extension-level detail). Individual node class inventories are large (Impact Pack alone exposes dozens). For architecture purposes, the packs and why they matter:

| Pack | Why it exists / typical use | Used by Wan Studio app graphs? |
|------|-----------------------------|--------------------------------|
| `wan_studio_i2i` | True Wan22 img2img latent helper | **NO** |
| `ComfyUI-GGUF` | Load GGUF quantized UNETs | **NO** (app uses safetensors fp8) |
| `ComfyUI-Impact-Pack` | Face detailers, detectors, iterative upscale | **NO** |
| `ComfyUI-Impact-Subpack` | Ultralytics detector provider | **NO** |
| `ComfyUI-Manager` | Install/update nodes & models UI | Ops only |
| `ComfyUI-ReActor` | Face swap / restore | **NO** |
| `ComfyUI-VideoHelperSuite` | Video combine/load helpers | **NO** (app uses core CreateVideo/SaveVideo) |
| `comfyui_controlnet_aux` | ControlNet preprocessors (depth/pose/etc.) | **NO** |
| `ComfyUI_essentials` | Misc quality-of-life nodes | **NO** |
| `ComfyUI_IPAdapter_plus` | IPAdapter identity/style | **NO** |
| `ComfyUI_PuLID_Flux_ll` | PuLID for Flux face ID | **NO** |
| `ComfyUI_UltimateSDUpscale` | Tiled upscale | **NO** |
| `rgthree-comfy` | UX/graph utility nodes | **NO** |

---

# 11. Installed ComfyUI Extensions

Exact directories under:

`E:\Comfy-Desktop\ComfyUI-Installs\Khelukhiladi\ComfyUI\custom_nodes`

1. `ComfyUI-GGUF` — GGUF model loading (`comfyui-gguf` v2.0.0 metadata)
2. `ComfyUI-Impact-Pack` — detectors/detailers/upscalers (v8.28.3 metadata)
3. `ComfyUI-Impact-Subpack` — UltralyticsDetectorProvider (v1.3.5)
4. `ComfyUI-Manager` — ComfyUI Manager
5. `ComfyUI-ReActor` — ReActor face tools
6. `ComfyUI-VideoHelperSuite` — video helper nodes
7. `comfyui_controlnet_aux` — ControlNet auxiliary preprocessors
8. `ComfyUI_essentials` — essentials node pack
9. `ComfyUI_IPAdapter_plus` — IPAdapter Plus
10. `ComfyUI_PuLID_Flux_ll` — PuLID Flux
11. `ComfyUI_UltimateSDUpscale` — Ultimate SD Upscale
12. `rgthree-comfy` — rgthree utilities
13. `wan_studio_i2i` — project custom node

Also present (not packs): `__pycache__`, `example_node.py.example`, `websocket_image_save.py`.

**Shared model path config:** `extra_model_paths.yaml` maps to `E:/Comfy-Desktop/ComfyUI-Shared/`.

---

# 12. Requirements

## 12.1 Application `requirements.txt` (exact)

```
fastapi==0.115.12
uvicorn[standard]==0.34.2
python-multipart==0.0.20
motor==3.7.0
pymongo==4.12.0
httpx==0.28.1
websockets==15.0.1
python-dotenv==1.1.0
pydantic==2.11.3
pydantic-settings==2.9.1
Pillow==11.2.1
aiofiles==24.1.0
deep-translator==1.11.4
```

## 12.2 Frontend `package.json` (exact dependencies)

**dependencies**

```
react: ^19.2.8
react-dom: ^19.2.8
```

**devDependencies**

```
@types/react: ^19.2.17
@types/react-dom: ^19.2.3
@vitejs/plugin-react: ^6.0.4
oxlint: ^1.75.0
vite: ^8.2.0
```

**scripts**

```
dev: vite
build: vite build
lint: oxlint
preview: vite preview
```

## 12.3 Python version (application)

| Source | Value |
|--------|-------|
| `.python-version` | `3.12.8` |
| `runtime.txt` | `python-3.12.8` |
| `render.yaml` `PYTHON_VERSION` | `3.12.8` |

## 12.4 ComfyUI runtime (machine, not pinned in app repo)

| Item | Value |
|------|-------|
| ComfyUI venv Python | **3.13.12** |
| Torch | **2.10.0+cu130** |
| Torchvision | **0.25.0+cu130** (from `requirements-nvidia.txt`) |
| Torchaudio | **2.10.0+cu130** |
| CUDA | **13.0** |
| GPU | NVIDIA GeForce **RTX 5060 Ti** |
| NVIDIA requirements file | `E:\Comfy-Desktop\ComfyUI-Installs\Khelukhiladi\requirements-nvidia.txt` pins cu130 wheels |

The **application backend does not depend on Torch**. Torch runs only inside ComfyUI.

---

# 13. Environment Variables

## 13.1 Backend (from `.env.example` + `backend/config.py`)

| Variable | Default | Meaning |
|----------|---------|---------|
| `APP_HOST` | `0.0.0.0` | Uvicorn bind host |
| `APP_PORT` | `8000` | Uvicorn bind port |
| `CORS_ORIGINS` | `*` | Allowed browser origins (`*` or comma-separated) |
| `SERVE_FRONTEND` | `false` | If true, serve `frontend/dist` from FastAPI |
| `MONGODB_URI` | **required** | Mongo connection string |
| `MONGODB_DB` | `wan_studio` | Database name |
| `COMFYUI_URL` | `http://127.0.0.1:8188` | ComfyUI base URL (local or Cloudflare tunnel) |
| `COMFYUI_TIMEOUT_SEC` | `1200` | Max seconds waiting on Comfy WS |
| `COMFYUI_DIR` | empty/`None` | Local filesystem root for scrubbing; auto-detect from `/system_stats` argv if possible |
| `ZERO_RESIDUE` | `true` | Enable post-job secure wipe |
| `SCRUB_PASSES` | `1` | Overwrite passes before unlink |
| `SCRUB_CLEAR_ALL_HISTORY` | `true` | Clear entire Comfy history after jobs |
| `FLUX_UNET` | `flux1-dev-fp8.safetensors` | Flux UNET filename |
| `FLUX_CLIP_L` | `clip_l.safetensors` | CLIP-L filename |
| `FLUX_T5` | `t5xxl_fp8_e4m3fn.safetensors` | T5 XXL filename |
| `FLUX_VAE` | `ae.safetensors` | Flux VAE filename |
| `FLUX_GUIDANCE` | `3.5` | FluxGuidance value |
| `IMAGE_WIDTH` | `1024` | Max width box for img |
| `IMAGE_HEIGHT` | `1024` | Max height box for img |
| `IMAGE_DENOISE` | `0.42` | Img2img denoise (clamped 0.28–0.55 in builder) |
| `SAMPLER_STEPS` | `28` | Flux KSampler steps |
| `WAN_UNET_HIGH` | `wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors` | Wan high-noise UNET |
| `WAN_UNET_LOW` | `wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors` | Wan low-noise UNET |
| `WAN_VAE` | `wan_2.1_vae.safetensors` | Wan VAE filename |
| `WAN_CLIP` | `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | Wan text encoder |
| `WAN_SHIFT` | `5.0` | ModelSamplingSD3 shift |
| `VIDEO_WIDTH` | `640` | Max width box for video |
| `VIDEO_HEIGHT` | `640` | Max height box for video |
| `VIDEO_LENGTH` | `49` | Frame count |
| `VIDEO_FPS` | `16` | Output FPS |
| `VIDEO_STEPS` | `20` | Total dual-stage steps |
| `VIDEO_CFG` | `3.5` | CFG both stages |
| `WAN_UNET` | legacy alias default high noise | Kept for old `.env`; **ignored by new workflows** |
| `CFG` | `3.5` legacy | Kept for old `.env`; **ignored by new workflows** |

## 13.2 Frontend

| Variable | Default | Meaning |
|----------|---------|---------|
| `VITE_API_URL` | empty | Production API origin; empty uses same-origin / Vite proxy |

## 13.3 Render-specific (from `render.yaml`)

Sets many of the above as service env defaults; secrets marked `sync: false`:

- `MONGODB_URI` (secret)
- `COMFYUI_URL` (secret)
- `CORS_ORIGINS` (secret)
- Plus all model/size defaults listed in `render.yaml`

---

# 14. ComfyUI Manager — Installed Models & Nodes

ComfyUI Manager itself is installed (`ComfyUI-Manager`). There is no Manager database export checked into this repo. The following is the **on-disk inventory** of what Manager (or manual install) has effectively made available.

## 14.1 Installed models (complete weight inventory found)

### Shared (`E:\Comfy-Desktop\ComfyUI-Shared\models`)

**checkpoints/**

- `ltx-2.3-22b-dev-fp8.safetensors`

**diffusion_models/**

- `flux1-dev-fp8.safetensors`
- `wan2.1_t2v_1.3B_fp16.safetensors`
- `Wan2.2-T2V-A14B-HighNoise-Q5_K_M.gguf`
- `Wan2.2-T2V-A14B-LowNoise-Q5_K_M.gguf`
- `wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors`
- `wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors`
- `wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors`
- `wan2.2_t2v_low_noise_14B_fp16.safetensors`
- `wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors`
- `wan2.2_ti2v_5B_fp16.safetensors`
- `z_image_turbo_bf16.safetensors`

**text_encoders/**

- `clip_l.safetensors`
- `EVA02_CLIP_L_336_psz14_s6B.pt`
- `gemma_3_12B_it_fp4_mixed.safetensors`
- `qwen_3_4b.safetensors`
- `t5xxl_fp8_e4m3fn.safetensors`
- `umt5_xxl_fp8_e4m3fn_scaled.safetensors`

**vae/**

- `ae.safetensors`
- `wan2.2_vae.safetensors`
- `wan_2.1_vae.safetensors`

**loras/**

- `gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors`
- `ifrgirl_wan22_low.safetensors`
- `Instagirlv2.0_hinoise.safetensors`
- `Instagirlv2.0_lownoise.safetensors`
- `Lenovo.safetensors`
- `ltx_2.3_22b_distilled_1.1_lora_dynamic_fro09_avg_rank_111_bf16.safetensors`
- `wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors`
- `wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors`
- `wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors`
- `wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors`
- `Wan21_T2V_14B_lightx2v_cfg_step_distill_lora_rank32.safetensors`

**upscale_models/**

- `4x-UltraSharp.pth`

**latent_upscale_models/**

- `ltx-2.3-spatial-upscaler-x2-1.1.safetensors`

**ultralytics/**

- `bbox/face_yolov8m.pt`

**Empty / no weights found in scan:** `clip_vision`, `controlnet`, `sams`, `ipadapter` (as dedicated folder), `embeddings`, etc.

### Local install extras (`...\ComfyUI\models`)

- `pulid/pulid_flux_v0.9.1.safetensors`
- Face detection / restore / insightface / content classifier / ultralytics face weights listed in §5.2

## 14.2 Installed nodes (extension packs)

See §10.2 and §11 — Manager-visible custom node packs are those 13 directories.

Core ComfyUI nodes used by the app are built-in and do not appear as Manager “custom nodes.”

---

# 15. Weakness Analysis

Quality and architecture problems that reduce output quality relative to ChatGPT Images / Kling / Magnific / Krea-class results:

## 15.1 Image editing weaknesses

1. **No masking / inpainting** — edits are global denoise; local changes bleed into face/background.
2. **No semantic understanding** — no Florence2 / GroundingDINO / SAM2 to locate “shirt”, “sky”, “face”.
3. **No PuLID / IPAdapter / InstantID in graph** — despite PuLID weights + IPAdapter pack installed; identity lock is prompt-only.
4. **No FaceDetailer / ReActor / GFPGAN / CodeFormer pass** — face restore models installed but unused.
5. **FP8 Flux Dev** — quantization softens fine detail vs bf16/fp16 Flux Dev.
6. **Sampler/scheduler choice** — hardcoded `euler` + `simple`; often suboptimal vs community Flux edit presets (`euler`/`beta`, `deis`, higher guidance tuning).
7. **Guidance 3.5 / denoise 0.42** — middle ground that frequently either under-edits or drifts identity; no adaptive denoise by edit type.
8. **No ControlNet** — cannot lock pose/depth/edges; `controlnet_aux` installed but **no ControlNet weights**.
9. **No upscale / finish pass** — `4x-UltraSharp` and UltimateSDUpscale installed but unused; outputs stay at ≤1024.
10. **Prompt engineering is regex + translate** — not vision-language rewrite; weak vs proprietary edit planners.
11. **Negative prompts not exposed in UI** — users cannot steer artifacts.
12. **Seed not exposed in UI** — poor reproducibility for quality iteration.
13. **Custom Wan img2img node unused** — IMG abandoned Wan path without building a stronger Flux edit stack to replace it.
14. **Iterative edits re-encode repeatedly** — each loop adds compression/VAE drift.

## 15.2 Video weaknesses

1. **640×640 class resolution** — far below Kling / commercial I2V defaults.
2. **~3 seconds at 16fps** — short clips; no extension / sliding window.
3. **Only 20 steps** — quality headroom left on table (unless using distill LoRAs, which are **not** applied).
4. **LightX2V 4-step LoRAs installed but unused** — neither fast distilled path nor a high-step quality path is optimized.
5. **No frame interpolation** — 16fps can look stuttery vs interpolated 24/30/48.
6. **No video upscaler** — no 720p/1080p finish.
7. **Using `wan_2.1_vae` while `wan2.2_vae` exists** — possible mismatch vs Wan 2.2 expectations (needs validation; risk of softness/color issues).
8. **No camera control / motion brush / trajectory** — motion is text-only.
9. **No face identity module for video** — talking/moving faces drift.
10. **euler/simple both stages** — may not be best Wan 2.2 preset (community often tunes uni_pc / other schedulers and shifts).
11. **No last-frame / keyframe control**.

## 15.3 System / product weaknesses affecting perceived quality

1. **Synchronous HTTP generation** — timeouts/retries cause failed jobs; no progress UX.
2. **No async job queue with previews** — user cannot steer mid-generation.
3. **Tunnel dependency** — Cloudflare quick tunnels change URL; flaky connectivity → failed gens.
4. **No auth / tenancy** — not a quality issue per se, but blocks safe multi-user A/B quality testing in prod.
5. **Extensions installed but disconnected from app** — machine has SOTA-ish tools; product uses a minimal subset.
6. **Empty `clip_vision` and `controlnet` model folders** — IPAdapter/ControlNet cannot work even manually without downloading weights.
7. **No Magnific-style creative upscale / degrade-recover pipeline**.
8. **No multi-pass “plan → edit → refine → upscale” agent**.

---

# 16. Improvement Plan

## 16.1 Current architecture (as-is)

```
React SPA
  → FastAPI orchestrator (sync)
    → prompt regex/translate
    → ComfyUI
         IMG: Flux Dev FP8 global img2img (13 nodes)
         VID: Wan 2.2 I2V 14B dual KSampler (15 nodes)
    → Mongo GridFS library
    → wipe local Comfy files
```

Strengths to keep:

- Clean separation of UI / API / Comfy
- GridFS as single media source of truth
- Dual-expert Wan I2V structure is the correct Wan 2.2 pattern
- FluxGuidance + CFG=1 is correct Flux wiring
- Zero-residue ops model

## 16.2 Problems (condensed from §15)

- Editing is **global denoise**, not localized surgical editing
- Identity stacks installed but **not connected**
- Finish stacks (upscale, face restore, interpolation) installed but **not connected**
- Quantized models + modest steps/resolution
- Prompt path has **no vision model**
- Video resolution/fps/length too low for commercial feel

## 16.3 Why output quality is poor (relative to ChatGPT Images / Kling / Magnific / Krea)

| Competitor trait | Your system today |
|------------------|-------------------|
| ChatGPT Images: understands request + local edit + strong identity | Regex prompt + full-frame Flux denoise |
| Krea: interactive latent control / fine local edits | No mask, no live latent UI |
| Magnific: specialized upscale/creativity pass | No upscale pass |
| Kling: high-res temporal coherence + motion control | 640px, 3s, text-only motion, no interp |

Quality is limited less by “missing a random node” and more by **missing multi-stage pipelines** that those products run invisibly.

## 16.4 Exactly which nodes should be removed (from the product path)

Do **not** necessarily uninstall packs from ComfyUI; remove/avoid them from the **default app-generated graphs** when they hurt fidelity or add instability:

1. **Do not route IMG through unused/experimental Wan TI2V img2img** unless rebuilt carefully — keep Flux for photoreal edits OR rebuild a proper masked Wan path; the current unused `Wan22ImageToImageLatent` should not be naively swapped back in as a full editor.
2. **Avoid style LoRAs** (`Instagirl*`, `ifrgirl*`, `Lenovo`) in the default identity-preserving edit path — they fight photoreal identity.
3. **Avoid ReActor face-swap as a default** for “edit my photo” — swap ≠ preserve; use PuLID/FaceDetailer instead.
4. **Avoid forcing LightX2V 4-step LoRAs** on a 20-step quality profile (either commit to 4-step distilled OR full steps without distill LoRA — do not mix casually).

## 16.5 Exactly which nodes should be added (to app workflows)

### Image edit graph (rebuild)

Add a multi-pass graph approximately:

```
LoadImage
↓
(optional) Florence2 / Qwen2.5-VL caption + edit plan   [ADD — download model]
↓
GroundingDINO / text-to-box for subject phrases         [ADD — download model]
↓
SAM2 / SAM segment from boxes                           [ADD — download model]
↓
Mask blur / grow
↓
DualCLIP + UNET Flux (prefer higher precision weights)
↓
PuLID Flux apply (face embed from start image)          [ADD to graph — weights already present]
↓
(optional) IPAdapter Plus face/style low weight         [ADD — need clip_vision weights]
↓
(optional) ControlNet canny/depth lock                  [ADD — need ControlNet Flux models]
↓
VAEEncode
↓
SetLatentNoiseMask / InpaintModelConditioning
↓
KSampler (inpaint denoise localized)
↓
VAEDecode
↓
Impact FaceDetailer (Ultralytics face_yolov8m already present)
↓
(optional) CodeFormer / GFPGAN light restore
↓
UltimateSDUpscale or 4x-UltraSharp finish
↓
SaveImage
```

### Video graph (upgrade)

```
LoadImage
↓
(optional) face ID / IPAdapter conditioning for Wan if available
↓
WanImageToVideo @ higher res (832×480 / 720×1280 class as VRAM allows)
↓
LoRA stack ONLY if using dedicated quality or dedicated speed profile
↓
Dual KSamplerAdvanced (tune sampler/scheduler/shift)
↓
VAEDecode (evaluate wan2.2_vae vs wan_2.1_vae)
↓
Video Helper Suite / interpolation (RIFE) to 24–30fps   [ADD interpolation models]
↓
Upscale frames (4x-UltraSharp or video upscaler) to 1080p class
↓
Encode high-bitrate mp4
↓
SaveVideo
```

## 16.6 Exactly which models should be replaced / added

### Replace / upgrade

| Current | Action |
|---------|--------|
| `flux1-dev-fp8.safetensors` | Prefer **Flux Dev fp16/bf16** or validated higher-quality quant; keep fp8 only as low-VRAM fallback profile |
| `wan_2.1_vae.safetensors` as default | A/B test **`wan2.2_vae.safetensors`**; set winner as `WAN_VAE` |
| 640×640 video default | Raise toward **720p-class** presets when VRAM allows |
| 20 steps video default | Offer **Quality profile 30–40** steps OR distilled **4-step LightX2V** profile (separate) |

### Add (download)

| Model | Purpose |
|-------|---------|
| Florence-2 large / Qwen2.5-VL / equivalent | Edit understanding + prompt planning |
| GroundingDINO | Text → boxes |
| SAM2 | Boxes → masks |
| Flux ControlNet (canny/depth/union) | Structure lock |
| IPAdapter face / PLUS clip_vision (`CLIP-ViT-H`, etc.) | Identity/style |
| RIFE / FILM weights | Video interpolation |
| (optional) Flux Fill / inpaint-specific UNet if using dedicated inpaint workflow | Cleaner local edits |

### Already on disk — wire into graphs

| Model | Action |
|-------|--------|
| `pulid_flux_v0.9.1.safetensors` | Add PuLID nodes to Flux edit graph |
| `4x-UltraSharp.pth` | Final upscale pass |
| `face_yolov8m.pt` + Impact Pack | FaceDetailer pass |
| `codeformer` / `GFPGAN` | Optional face refine |
| `wan2.2_i2v_lightx2v_4steps_lora_v1_{high,low}_noise` | Dedicated **Fast** video profile only |

## 16.7 Exactly which workflows should be rebuilt

1. **`build_i2i_prompt` → replace with `build_flux_inpaint_identity_prompt`**
   - Masked inpaint + PuLID + FaceDetailer + upscale
   - Keep a “simple global img2img” profile only as fallback

2. **Add `build_flux_kontext_or_fill_prompt` (optional second IMG engine)**
   - If adopting Flux Kontext / Fill family models for instruction edits — closer to ChatGPT-style edit behavior than denoise img2img

3. **`build_i2v_prompt` → split into profiles**
   - `fast`: LightX2V 4-step LoRAs, lower res
   - `quality`: more steps, higher res, interp, upscale
   - Evaluate `wan2.2_vae`

4. **Add post job `build_upscale_prompt`**
   - Dedicated Magnific-like creative/conservative upscale workflow using UltimateSDUpscale + UltraSharp

5. **Deprecate relying on prompt-only identity wrappers** as the primary defense

6. **Repo custom node `Wan22ImageToImageLatent`**
   - Keep for experimental Wan still edits
   - Do not make it the production photoreal editor unless paired with masks + face lock

## 16.8 Target architecture for SOTA-like local quality

```
UI
 ↓
API job queue (async) + progress events
 ↓
Planner (VLM): understand image + user intent → structured edit plan
 ↓
Localizer (GroundingDINO + SAM2): masks / regions
 ↓
Generator:
   IMG: Flux (high precision) + PuLID + ControlNet + masked inpaint
   VID: Wan 2.2 I2V dual expert @ higher res + optional ID conditioning
 ↓
Refiner: FaceDetailer / light restore
 ↓
Finisher: upscale (+ video interpolation)
 ↓
GridFS store + scrub
```

Still fully local:

- No required cloud LLM if VLM runs locally (Qwen2.5-VL / Florence2)
- ComfyUI remains the execution engine
- FastAPI becomes a **pipeline orchestrator** submitting multi-graph jobs, not a single 13-node graph

### Parameter targets (starting points to tune on RTX 5060 Ti)

**IMG quality profile**

- Flux precision: fp16/bf16 if VRAM allows, else fp8 fallback
- Guidance: tune 3.5→5.0 for stubborn edits
- Inpaint denoise: 0.45–0.75 **inside mask only**
- Outside mask: denoise 0
- Steps: 28–40
- Sampler candidates: euler / deis; schedulers: simple / beta / sgm_uniform — A/B
- PuLID weight: start ~0.6–0.9
- Upscale: 1.5×–2× UltraSharp / USDU

**VID quality profile**

- Resolution: 832×480 or 720×1280 class
- Length: 49–81 frames
- FPS encode: 24 after interpolation from 16
- Steps: 30–40 without distill LoRA, or 4 with LightX2V
- CFG: 3–4
- Shift: tune around 5.0
- Always run face-aware refine on frames if faces dominate

## 16.9 Implementation order (practical)

1. Wire **PuLID + FaceDetailer + UltraSharp** into IMG graph (weights already local)  
2. Add **mask inpaint** path (even manual mask from UI before auto-segmentation)  
3. Download **Florence2/SAM2/GroundingDINO** and automate masks  
4. Raise **video res + interpolation + upscale**  
5. Add async jobs + progress so longer SOTA pipelines are usable  
6. Add quality profiles (fast/quality) instead of one compromised default  
7. Only then chase model swaps (Flux fp16, Wan VAE, Kontext/Fill)

---

# Appendix A — Frontend generate request vs backend capabilities

| Capability | Backend | Frontend UI |
|------------|---------|-------------|
| mode img/vid | yes | yes |
| prompt | yes | yes |
| image upload | yes | yes |
| negative | yes | **no field** |
| seed | yes | **no field** |
| progress % | no | no |
| cancel job | no | no |

# Appendix B — Default negatives (full text)

See §7.4 for complete `DEFAULT_NEGATIVE_FLUX` and `DEFAULT_NEGATIVE_WAN` strings as hardcoded in `backend/workflows_wan.py`.

# Appendix C — Scrub filename prefixes

```
wan_in_
wan_i2i
wan_i2v
ComfyUI_temp
(+ any name starting with wan_ or containing wan_i)
```

Save prefixes from workflows:

- Images: `flux_i2i`
- Videos: `wan_i2v14`

---

**End of report.**  
This document is the complete extraction of the application architecture, the two production ComfyUI workflows node-by-node, the local ComfyUI extension/model inventory, and the quality gap analysis with a concrete rebuild plan toward local SOTA-like results.

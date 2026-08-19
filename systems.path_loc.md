# System path locations — generation traces

Where Wan Studio / ComfyUI **can leave hints** of prompts, images, or videos.
Cloud storage is intentional; local paths below are what matter for PC residue.

Canonical Comfy root (from `.env` `COMFYUI_DIR`):

`E:\Comfy-Desktop\ComfyUI-Installs\Khelukhiladi\ComfyUI`

---

## 1. High priority — check these first (imgs / vids / mid-run leftovers)

| Path | What can be there | After successful job |
|------|-------------------|----------------------|
| `E:\Comfy-Desktop\ComfyUI-Installs\Khelukhiladi\ComfyUI\input` | Uploaded start images (`wan_in_…`) | Scrubbed via **remote** `/wan_studio/scrub` on Comfy |
| `E:\Comfy-Desktop\ComfyUI-Installs\Khelukhiladi\ComfyUI\output` | Generated images / videos (`flux_*`, `wan_i2v14*`, …) | Same |
| `E:\Comfy-Desktop\ComfyUI-Installs\Khelukhiladi\ComfyUI\temp` | Temp frames / intermediates | Same |

**Why files used to pile up:** the API runs on **Render**. It cannot see `E:\…` on this PC. Old scrub only did a local `Path` wipe, which silently no-oped in production. History clear over HTTP still worked; **disk files stayed**.

**Fix:** Comfy custom node `wan_studio_i2i` exposes `POST /wan_studio/scrub`. After each job the API calls that over the tunnel so this PC deletes the files. **Restart ComfyUI** after updating that node so the route loads.

**Risk remaining:** mid-run crash / Comfy not restarted with the scrub node / tunnel down before scrub runs.

---

## 2. Medium — text / history / logs (usually not media)

| Path | What it is | Trace risk |
|------|------------|------------|
| `E:\Comfy-Desktop\ComfyUI-Installs\Khelukhiladi\ComfyUI\user\` | Comfy user data folder | Mixed (see below) |
| `…\user\comfyui.log` | Live log | Startup / errors; rarely full prompts |
| `…\user\comfyui.prev.log` | Rotated log | Same |
| `…\user\comfyui.prev2.log` | Older rotated log | Same |
| `…\user\comfyui_8188.log` (+ `.prev`, `.prev2`) | Port **8188** instance logs (Wan’s usual port) | Same |
| `…\user\comfyui_8189.log` (+ `.prev`, `.prev2`) | Other Comfy port logs | Same |
| `…\user\comfyui_8197.log` / `_8198` / `_8199` | Other instance logs | Same |
| `…\user\comfyui.db` | Comfy/Manager DB (settings/state) | Not your media library |
| `…\user\comfyui.db.bkp` | DB backup | Same |
| `…\user\comfyui.db.lock` | Lock file while Comfy runs | Empty / ignore |
| `…\user\__manager\` | ComfyUI-Manager config/cache | Not gens |
| `…\user\default\` | UI settings (`comfy.settings.json`, etc.) | Not gens |

Comfy **prompt history** (workflow JSON including prompt text) lives in Comfy’s runtime history API / UI state. The app clears it after jobs when scrub is on (`SCRUB_CLEAR_ALL_HISTORY=true`). If scrub didn’t run, reopen Comfy → History and clear manually.

---

## 3. Low / not generation content (ignore for media residue)

| Path | Notes |
|------|--------|
| `E:\Comfy-Desktop\ComfyUI-Shared\models\` | Models / LoRAs only — not your prompts or outputs |
| `E:\Comfy-Desktop\ComfyUI-Shared\models\loras\` | Video/image LoRA weights |
| `d:\YtAuto\contrnt\` | App source code |
| `d:\YtAuto\contrnt\.env` | Config + secrets (URIs, keys) — **not** gen media, but sensitive |
| `d:\YtAuto\contrnt\tokens&cmd` | Deploy tokens — sensitive, not gens |

---

## 4. This PC — other places that can mention / show gens

| Path | What |
|------|------|
| `C:\Users\User\.cursor\projects\d-YtAuto-contrnt\agent-transcripts\` | Cursor chat transcripts (can include pasted prompts) |
| Browser profile cache (only if you open Wan **on this PC**) | Cached preview images/videos from the SPA |
| Downloads folder | Only if you explicitly downloaded a generation |
| `d:\YtAuto\contrnt\videoedits.md` | Local notes you kept (if present) — not auto-written by Comfy |

---

## 5. Cloud — intentional storage (not on PC disk as primary)

These hold lasting prompts + media by design:

| Service | Role |
|---------|------|
| MongoDB Atlas (`wan_studio`) | `jobs` (prompts/status), `generations` + GridFS media |
| Cloudinary | Mirrored image/video CDN URLs |
| Render API | `https://wan-studio-api.onrender.com` — process memory only while running |
| Vercel frontend | `https://frontend-six-chi-37.vercel.app` — no server-side prompt store; device may keep PIN session in browser `localStorage` |

---

## 6. Quick hygiene checklist

1. **Restart ComfyUI** after installing/updating `custom_nodes/wan_studio_i2i` (loads `/wan_studio/scrub`).
2. Confirm scrub endpoint: open or curl  
   `http://127.0.0.1:8188/wan_studio/scrub_ping` → `{"ok": true, ...}`
3. Optional full wipe: `POST https://wan-studio-api.onrender.com/api/scrub`  
   (or local API) — clears prefixes under input/output/temp + Comfy history.
4. Open and verify empty:  
   `…\ComfyUI\input` · `…\ComfyUI\output` · `…\ComfyUI\temp`
5. Optional: delete old `…\user\comfyui*.log` / `.prev*` (clutter only).
6. Don’t delete `comfyui.db` unless you want to reset Comfy UI settings.
7. Remember Cursor chats on this PC can still contain prompt text.

---

## 7. How scrub maps to these folders

App settings (local `.env` / Render env):

- `ZERO_RESIDUE=true` — after each job, wipe matching artifacts
- Remote path (production): API → tunnel → Comfy `POST /wan_studio/scrub`
- Local path (dev only): `COMFYUI_DIR` Path wipe when API shares the disk with Comfy
- `SCRUB_CLEAR_ALL_HISTORY=true` — clear Comfy history after jobs
- Manual: `POST /api/scrub`

Prefixes wiped (safety net): `wan_in_`, `wan_i2i`, `wan_i2v*`, `flux_i2i`, `flux_kontext`, plus listed job outputs.

**“Zero residue” = local Comfy disk after a finished job**, not “nothing stored in the cloud.”

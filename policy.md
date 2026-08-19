# Policy & Sanitization Plan

Compliance guide for **Wan Studio** (Maal): how to keep using the app privately while reducing GitHub, hosting, and legal exposure. This is operational guidance, not legal advice.

**Goals**

1. Repo and deployments pass platform acceptable-use rules (GitHub, Render, etc.).
2. App remains fully usable for **private, PIN-gated** personal use from any device.
3. Explicit presets, prompts, and generated media never live in git or on policy-sensitive CDNs.

---

## 1. Risk model (what actually triggers action)

| Trigger | GitHub | Vercel | Render | Telegram | Legal |
|--------|--------|--------|--------|----------|-------|
| Explicit prompt text in committed source | **High** | **High** (in JS bundle) | Medium (logs/requests) | Low (gitignored bot config) | — |
| Public URL + no auth | — | Medium | Medium | Low (DM + whitelist) | — |
| Streaming generated explicit media through host | — | Low | **High** | Medium (via API fetch) | — |
| NCII-style edits of real people without consent | Medium (tooling) | **High** | **High** | **High** | **Highest** |
| Private repo + auth + sanitized source | Low | — | Low–Medium | Low | Consent still applies |

**Intent (“personal use only”) does not exempt you from ToS or law.** It mainly reduces discovery and abuse reports.

---

## 2. Target compliant architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  SANITIZED REPO (GitHub private or public)                      │
│  Generic ComfyUI orchestration · img2img / i2v · PIN auth       │
│  No explicit presets · no graphic prompts · neutral docs        │
│  Optional: scripts/telegram_bot.py (generic client, no presets) │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  PRIVATE RUNTIME (never committed)                              │
│  • WAN_PINS, WAN_AUTH_SECRET (Render env)                       │
│  • TELEGRAM_BOT_TOKEN, ALLOWED_TELEGRAM_IDS                       │
│  • presets.private.json → MongoDB `presets` collection          │
│  • Optional: prompt templates in GridFS or gitignored private/  │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
   Telegram bot       Render (API only)     MongoDB Atlas
   (DM, whitelist)     jobs + auth           media + presets
        │                    │
        └──────────► Home GPU (ComfyUI) ◄──────┘
```

**Recommended access for multi-device private use**

| Priority | Frontend | API | Who can reach it |
|----------|----------|-----|------------------|
| **Best for phone** | **Telegram bot** (DM only) | Local or Render | Your Telegram user ID only |
| **Best privacy** | `SERVE_FRONTEND=true` on home PC | Same host | Tailscale only |
| **Good balance** | Same Render service as API | Render | PIN + bookmarked URL |
| **Avoid** | Vercel Hobby with explicit bundle | Render streaming `/api/media` | Public discovery |

---

## 3. Private data boundary

Everything below is **runtime-only**. Never commit, never paste in issues/PRs, never screenshot in public docs.

| Asset | Store where | Git |
|-------|-------------|-----|
| PIN hashes | Render env `WAN_PINS` | ❌ |
| Auth secret | Render env `WAN_AUTH_SECRET` | ❌ |
| Telegram bot token | `tokens&cmd` or `.env` (`TELEGRAM_BOT_TOKEN`) | ❌ |
| Allowed Telegram user IDs | Bot env `ALLOWED_TELEGRAM_IDS` | ❌ |
| Action presets (labels + prompts) | MongoDB or gitignored `private/presets.json` | ❌ |
| Review bin labels (tester QA) | MongoDB or gitignored `private/review_bins.json` | ❌ |
| Extra prompt scaffolds (long templates) | Gitignored `private/prompt_templates/` or DB | ❌ |
| Generated images/videos | MongoDB GridFS | ❌ (already) |
| User uploads (job inputs) | MongoDB GridFS (ephemeral) | ❌ |
| LoRA weights | GPU disk / HF download scripts | ❌ (filenames OK in catalog) |
| Tunnel URLs | Render env `COMFYUI_URL` | ❌ |

### Add to `.gitignore`

```
private/
*.private.json
presets.private.json
review_bins.private.json
```

---

## 4. GitHub sanitization plan

### 4.1 Repository visibility

- [ ] Set repo to **Private** (`wellswenger-svg/Maal`) until sanitization is complete.
- [ ] After sanitization, you *may* go public again — only if verification checklist (§11) passes.

### 4.2 Remove or externalize explicit source

| File / area | Current issue | Sanitized shape |
|-------------|---------------|-----------------|
| `frontend/src/presets.js` | Full explicit labels + prompts | Empty stub or generic presets (`enhance`, `style`, `animate`); load real presets from `GET /api/presets` after PIN unlock |
| `frontend/src/reviewBins.js` | Explicit QA labels | Load from `GET /api/test/review-bins` or gitignored private file |
| `frontend/src/AgeGate.jsx` | Age-gate screen | **Removed** — app is a PIN-gated image/video editor |
| `backend/ai_engine/planner/rules.py` | Regex + reason codes name extra acts | Keep **generic** intent classes (`body_edit`, `fluid_overlay`, `motion_act`) — no graphic literals in comments |
| `backend/ai_engine/workflows/_shared/edit_runner.py` | Long explicit prompt templates | Move templates to DB/private files; code references template IDs only |
| `backend/ai_engine/workflows/video_i2v/motion.py` | Action scaffolds | Template IDs + private content |
| `backend/ai_engine/workflows/video_i2v/lora_stack.py` | Extra weight names | Logical IDs in repo; filenames only in private catalog override |
| `backend/ai_engine/models/catalog.py` | Extra Civitai/HF LoRA URLs | Split: public base models + gitignored private catalog override |
| `backend/ai_engine/tests/test_phase*.py` | Graphic prompt strings in tests | Neutral fixtures: `"apply template tpl_body_edit_v1"` |
| `scripts/download_*.py` | Extra LoRA download lists | Move to `private/` (gitignored) or document “configure locally” |
| `scripts/colab_comfy_bridge.ipynb` | Extra unlock examples | Generic Comfy bridge only, or move notebook to `private/` |
| `scripts/telegram_bot.py` | (future) | Generic API client only; presets from `private/presets.json` |
| `TECHNICAL.md`, `AI_ENGINE.md`, etc. | Product described as a private studio | Neutral: “private ComfyUI orchestration for img2img and i2v” |

### 4.3 Neutral README (replace missing root README)

Add a short `README.md`:

- One paragraph: Flux img2img + Wan i2v orchestration via ComfyUI.
- Private presets configured at runtime (not in repo).
- PIN auth required.
- No sample outputs, no preset names, no “adult” marketing.

### 4.4 Git history (optional, advanced)

If explicit content was ever pushed to **public** `main`, sanitizing current files is not enough — history still contains it.

- [ ] Option A: Keep repo **private** forever (simplest).
- [ ] Option B: New private repo + migrate sanitized tree (clean history).
- [ ] Option C: `git filter-repo` to purge paths — only if you understand force-push implications.

---

## 5. Leave Vercel (multi-device without Vercel)

Vercel hosts explicit strings in the static JS bundle. **Delete the Vercel project** after migration.

### Option A — Single URL on Render (simplest web UI)

1. Build frontend in Render deploy:
   ```yaml
   buildCommand: pip install -r requirements.txt && cd frontend && npm ci && npm run build
   ```
2. Render env:
   ```
   SERVE_FRONTEND=true
   CORS_ORIGINS=*
   VITE_API_URL=   # leave empty → same-origin /api
   ```
3. Open `https://wan-studio-api.onrender.com` on phone/laptop → PIN → use app.
4. PWA “Add to Home Screen” still works (manifest in `vite.config.js`).

### Option B — Tailscale (strongest privacy, web UI)

1. Home PC: `SERVE_FRONTEND=true`, `python run.py`.
2. Tailscale on PC + phone.
3. Browse `http://100.x.x.x:8000` — not on public internet.
4. Render optional: keep for jobs when home PC is off, or run API only on home PC.

### Option C — Cloudflare Tunnel to home PC (web UI)

Same as B but with `cloudflared tunnel --url http://127.0.0.1:8000`. Use a **named tunnel** so the URL is stable. Restrict with Cloudflare Access (email OTP) if desired.

### Option D — Telegram bot (recommended for phone; see §6)

No web frontend in production. Multi-device via Telegram app. **Prefer this** if your main workflow is: send photo → pick preset → get result.

**Update `PRODUCTION_URLS.md`** after migration; remove Vercel canonical URL.

---

## 6. Telegram bot (private remote UI)

A **personal Telegram bot** replaces the web frontend for multi-device use. The bot is a thin client over the existing Wan API — no React, no Vercel, no public URL with explicit JS.

### 6.1 Architecture

```
You (Telegram on phone / tablet / desktop)
    → scripts/telegram_bot.py (GPU PC or home server)
        → Wan API  http://127.0.0.1:8000  OR  https://wan-studio-api.onrender.com
            → ComfyUI (home GPU via tunnel)
            → MongoDB Atlas (library)
    ← bot sends result as photo / video in chat
```

| Step | Bot action | API |
|------|------------|-----|
| You send a photo | Download file from Telegram | — |
| You tap a preset (inline keyboard) | Start job | `POST /api/jobs` (`image`, `preset_id`, `prompt`, `mode`) |
| Waiting (minutes) | Edit message: “Job abc… 45%” | Poll `GET /api/jobs/{id}` |
| Done | Send result | `GET /api/media/{id}` → `sendPhoto` / `sendVideo` |
| Library browse (optional) | Paginated buttons | `GET /api/generations` |

Auth layers (use both):

1. **Telegram whitelist** — `ALLOWED_TELEGRAM_IDS=123456789` (reject all other users).
2. **Wan PIN / session** — bot calls `POST /api/auth/unlock` once at startup; sends `X-Wan-Token` on API requests (same as the web app).

Presets live in **`private/presets.json`** (or MongoDB after Phase 2). The committed `scripts/telegram_bot.py` only knows preset **IDs** and API wiring — not graphic prompt text.

### 6.2 Example chat flow

```
You:     [photo]
Bot:     Pick action:
         [Enhance] [Style] [Animate]
You:     [tap Enhance]
Bot:     ⏳ Job 7f3a… · image · ~3 min
Bot:     [result image]
```

Optional commands: `/library`, `/status`, `/cancel`, `/lock`.

### 6.3 Where to run the bot

| Host | When to use |
|------|-------------|
| **GPU PC** (recommended) | Same machine as ComfyUI; bot talks to `http://127.0.0.1:8000` — minimal cloud exposure |
| Home server / Raspberry Pi | Always-on; API local or via Tailscale |
| Render | Possible but **not recommended** — bot would still pull media through Render; prefer GPU PC |

Run alongside existing stack (see `scripts/gpu_agent.py` pattern):

```powershell
# GPU PC — add to tokens&cmd (gitignored):
# telegram_bot_token=123456:ABC…
# allowed_telegram_ids=YOUR_NUMERIC_ID

set TELEGRAM_BOT_TOKEN=…
set ALLOWED_TELEGRAM_IDS=123456789
set WAN_API_URL=http://127.0.0.1:8000
set WAN_PIN=your-pin
python scripts/telegram_bot.py
```

Get your numeric Telegram ID: message `@userinfobot` or `@getidsbot` once.

### 6.4 Bot env checklist

```
TELEGRAM_BOT_TOKEN=       # from @BotFather — never commit
ALLOWED_TELEGRAM_IDS=     # comma-separated; only these users
WAN_API_URL=              # http://127.0.0.1:8000 or Render URL
WAN_PIN=                  # unlock → session token for API calls
PRESETS_PATH=private/presets.json
POLL_INTERVAL_SEC=15      # job status poll
```

Add to `tokens&cmd` (gitignored):

```
telegram_bot_token=…
allowed_telegram_ids=123456789
```

### 6.5 Telegram limits

| Limit | Detail | Mitigation |
|-------|--------|------------|
| **50 MB file cap** | Default Bot API max upload/download | Shorten video; lower resolution; compress output |
| **2 GB files** | [Local Bot API server](https://core.telegram.org/bots/api#using-a-local-bot-api-server) on GPU PC | Run local server if videos exceed 50 MB |
| **Long jobs** | Video can take 20+ min | Async jobs already supported; edit status message while polling |
| **Media on Telegram servers** | Photos/videos pass through Telegram when sent | Accept for personal use; not “zero residue” |
| **No rich library UI** | Weaker than web grid / lightbox | `/library` with paginated inline keyboard; or keep web UI on Tailscale for browsing only |

### 6.6 Telegram policy (private bot)

From [Telegram Bot Developer ToS](https://telegram.org/tos/bot-developers):

- You are responsible for content your bot handles.
- **Prohibited:** violence, hate, harassment, **media belonging to unconsenting third parties**.
- User ToS: do not post **illegal content** on **publicly viewable** bots/channels.

**Private 1:1 DM with a whitelisted bot** is lower risk than a public bot or channel. Still does **not** exempt NCII/consent rules (§9).

Do **not**:

- Publish the bot username or add it to groups/channels.
- Register the bot with Telegram search/discovery.
- Share the bot link publicly.

### 6.7 Compliance benefits vs web UI

| Concern | Web (Vercel) | Telegram bot |
|---------|--------------|--------------|
| Explicit strings on CDN | In JS bundle | In gitignored `private/presets.json` only |
| Public discoverable URL | Yes | No — DM only |
| Multi-device | Browser | Telegram everywhere |
| GitHub repo | Frontend in git | Bot client generic; presets private |
| Render media streaming | Browser hits `/api/media` | Bot fetches media (same API path — see §7.2) |

**Best combo:** Telegram for daily generate-on-phone; Tailscale web UI optional for library/tester workflows.

### 6.8 Render: still needed?

| Setup | Render required? |
|-------|------------------|
| Bot + local API + ComfyUI on GPU PC (PC stays on) | **No** — MongoDB Atlas only |
| Phone away from home; GPU PC on with tunnel | **No** — bot on PC calls localhost API |
| GPU PC off; want jobs from phone | **Yes** — or wait until PC is on |

### 6.9 Implementation checklist

- [ ] Create bot via [@BotFather](https://t.me/BotFather); disable group privacy / keep bot unused in groups.
- [ ] Add `scripts/telegram_bot.py` (generic API client).
- [ ] Move preset labels/prompts → `private/presets.json`.
- [ ] Whitelist your Telegram user ID.
- [ ] Test: photo → preset → poll → receive image.
- [ ] Test video under 50 MB; plan Local Bot API if not.
- [ ] Add bot to `wan_stack_watchdog.py` or Task Scheduler so it restarts with Comfy.
- [ ] Delete Vercel project once bot works.
- [ ] Optional: retire React frontend from production entirely.

---

## 7. Render sanitization plan

Render ToS cares about **transmitting/hosting objectionable content**, not just code.

### 7.1 Required code changes (future PRs)

| Change | Why |
|--------|-----|
| `GET /api/presets` (auth required) | Frontend/bot never need explicit strings in git |
| Presets stored in MongoDB | Seeded from gitignored file on deploy |
| Redact `/api/health` public response | Stop exposing `comfyui_url` without auth |
| Rate-limit `/api/auth/unlock` | Slow brute-force on PIN |

### 7.2 Media delivery (high impact)

Today `/api/media/{id}` streams explicit bytes **through Render**. The Telegram bot uses the same endpoint when `WAN_API_URL` points at Render.

**Target:** Render returns a **short-lived signed URL** (MongoDB Atlas presigned, Cloudflare R2, or S3). Bot/browser fetches media directly from object storage. Render never proxies image/video bytes.

Until implemented:

- [ ] Keep PIN on all media routes (already done).
- [ ] Prefer **local API** (`http://127.0.0.1:8000`) from bot on GPU PC.
- [ ] Do not share media URLs outside your session.

### 7.3 Render env checklist

```
WAN_PINS=<bcrypt hashes>          # required — empty disables app
WAN_AUTH_SECRET=<long random>     # required
SERVE_FRONTEND=false              # when using Telegram bot (no web UI)
CORS_ORIGINS=*                    # bot is not browser-CORS; * OK for API-only
COMFYUI_URL=<tunnel>              # secret — not in git
MONGODB_URI=<secret>              # secret — not in git
RAW_PROMPT=true                   # user/private templates supply text
```

Set `SERVE_FRONTEND=true` only if you also want the web UI on Render (Option A).

### 7.4 Logging

- [ ] Confirm Render logs do not print full user prompts (audit `prompt_fix.py`, job creation).
- [ ] Truncate or hash prompts in structured logs if any are added later.

---

## 8. MongoDB Atlas, Cloudflare & Telegram

| Service | Action |
|---------|--------|
| **MongoDB Atlas** | Private cluster; IP allowlist or Atlas VPC; presets collection with explicit docs OK (not on GitHub). |
| **Cloudinary** (if enabled) | Explicit media on third-party CDN — prefer GridFS-only or private bucket. |
| **Cloudflare Tunnel** | ToS varies by product; personal tunnel to home lab is lower risk than publishing a site. Use Access gate. |
| **Telegram** | Private DM bot + whitelist; no public channels; consent rules still apply (§9). |
| **Colab** | Notebook already warns: adult content against ToS — use home GPU for private features. |

---

## 9. Legal & consent (non-platform, highest stakes)

Platform compliance ≠ lawful use.

**Rules for private operation**

1. **Only upload photos you own or have explicit written consent to alter** (including synthetic sexual edits).
2. **Never upload minors** — no age checkbox replaces verification.
3. **Do not impersonate or distribute** outputs of real people without consent.
4. Keep a local record of consent if editing photos of another adult.

The codebase should not encourage NCII in public docs; private presets are your responsibility. **Sending results through Telegram still counts as distribution** if you forward them to others without consent.

---

## 10. Implementation phases

### Phase 0 — Immediate (no code, ~30 min)

- [ ] GitHub repo → **Private**
- [ ] Confirm `WAN_PINS` + `WAN_AUTH_SECRET` set on Render
- [ ] Bookmark API URL; do not share
- [ ] Stop linking public GitHub in any public profile

### Phase 1 — Stop Vercel exposure (~1 h)

Pick **one** primary UI:

- [ ] **Telegram (recommended):** §6.9 checklist, then delete Vercel, **or**
- [ ] **Web:** Enable `SERVE_FRONTEND` + frontend build on Render (§5 Option A), verify from phone, delete Vercel

- [ ] Update `PRODUCTION_URLS.md` and `.cursor/rules/production-urls.mdc`

### Phase 1b — Telegram bot (~2–3 h)

- [ ] Implement `scripts/telegram_bot.py`
- [ ] Create `@BotFather` bot; set `TELEGRAM_BOT_TOKEN` + `ALLOWED_TELEGRAM_IDS`
- [ ] Copy presets → `private/presets.json`
- [ ] Run bot on GPU PC against local API
- [ ] Verify end-to-end from phone
- [ ] Add bot restart to watchdog / startup task

### Phase 2 — Externalize presets (~2–4 h)

- [ ] Add MongoDB `presets` collection + seed script reading `private/presets.json`
- [ ] Add `GET /api/presets` (requires PIN)
- [ ] Replace `frontend/src/presets.js` with API fetch + generic fallbacks (if keeping web UI)
- [ ] Point Telegram bot at `GET /api/presets` instead of local JSON
- [ ] Same pattern for `reviewBins.js` if tester mode stays

### Phase 3 — Sanitize backend (~4–8 h)

- [ ] Move long prompt templates out of `edit_runner.py` / `motion.py`
- [ ] Split model catalog: public base + private LoRA map
- [ ] Neutralize test fixtures
- [ ] Scrub docs (`TECHNICAL.md`, etc.)
- [ ] Add neutral `README.md`

### Phase 4 — Render hardening (~2–4 h)

- [ ] Signed URL media delivery (remove byte streaming through Render)
- [ ] Auth-gated health / hide tunnel URL
- [ ] Audit logs for prompt leakage

### Phase 5 — Optional maximum privacy

- [ ] Bot + local API only; Render as fallback or removed
- [ ] Tailscale for occasional web UI / tester tools
- [ ] New git history or fresh private repo
- [ ] Cloudflare Access in front of tunnel

---

## 11. Verification checklist

Run before making GitHub public again or sharing the repo.

### Git

```powershell
# No graphic sexual vocabulary in tracked files (private/ is gitignored)
rg -i "explicit|graphic" --glob '!private/**' --glob '!.git/**'
```

```powershell
# No media in repo
git ls-files '*.png' '*.jpg' '*.mp4'
# Should be empty (except frontend public icons if any)
```

### Deployed / runtime

- [ ] Web UI (if any): DevTools → search bundle for explicit strings → **none**
- [ ] Telegram bot: reject messages from non-whitelisted user IDs
- [ ] Without PIN: cannot list generations, cannot generate, cannot fetch media
- [ ] `/api/health` does not leak secrets (after Phase 4)

### Docs

- [ ] `README.md` is neutral
- [ ] `policy.md` describes private/runtime split (this file)
- [ ] No explicit screenshots in repo

### Operations

- [ ] `tokens&cmd`, `.env` gitignored and not in history
- [ ] `TELEGRAM_BOT_TOKEN` not in git
- [ ] MongoDB not publicly readable
- [ ] Consent rule understood for all uploads

---

## 12. API sketch (Phase 2)

Presets API — load after unlock; used by web UI and Telegram bot:

```
GET /api/presets
Authorization: X-Wan-Token: <session>
→ { "presets": [ { "id", "label", "hint", "mode", "prompt" } ] }
```

Seed once on deploy (admin script, not in git):

```bash
python scripts/seed_presets.py private/presets.json
```

`scripts/seed_presets.py` can live in repo (generic); **JSON content stays in `private/`**.

Telegram bot job flow (already exists on API):

```
POST /api/auth/unlock          → { "token", "owner" }
POST /api/jobs                 → multipart: mode, prompt, image, preset_id?
GET  /api/jobs/{id}            → { "status", "generation_id", … }
GET  /api/media/{gen_id}       → bytes (prefer signed URL after Phase 4)
```

---

## 13. What stays in the repo (safe)

These are fine to keep — generic ML orchestration:

- ComfyUI client, job queue, GridFS storage, scrub logic
- Flux / Wan workflow graphs (without explicit template text)
- PIN auth (`owners.py`, `PinGate.jsx`)
- Generic planner structure (intents as enums, not graphic regex literals)
- Download scripts that accept a manifest path argument
- Ops / watchdog / tunnel scripts
- **`scripts/telegram_bot.py`** — generic bot client (no preset text)
- Neutral architecture docs

---

## 14. Cursor / AI development note

You can keep using Cursor on this repo while complying:

- **Sanitized repo** = what the agent reads and commits.
- **`private/` folder** = gitignored; add real presets locally; never ask the agent to commit them.
- Reference preset IDs in code (`preset_id: "enhance"`) — OK if prompts live in DB/`private/` only.

---

## 15. Quick reference — current → target

| Item | Now | Target |
|------|-----|--------|
| GitHub visibility | Public | Private until §11 passes |
| Primary UI (phone) | Vercel web app | **Telegram bot** (whitelist) |
| Frontend host | Vercel | None, or Tailscale web for library |
| Presets | `presets.js` in git | `private/presets.json` + API |
| Media path | Render streams bytes | Local API or signed URL |
| Age gate | Present | **Removed** |
| Discovery | Public URLs | Whitelist + private repo |

---

## 16. Related files to update when executing phases

| Phase | Files |
|-------|-------|
| 1 / 1b | `scripts/telegram_bot.py` (new), `scripts/wan_stack_watchdog.py`, `PRODUCTION_URLS.md`, `.cursor/rules/production-urls.mdc` |
| 1 (web) | `render.yaml`, `PRODUCTION_URLS.md` |
| 2 | `backend/main.py`, `backend/db.py`, `frontend/src/presets.js`, `frontend/src/App.jsx`, `.gitignore` |
| 3 | `edit_runner.py`, `motion.py`, `rules.py`, `catalog.py`, tests, docs |
| 4 | `backend/main.py` (media), `backend/db.py` (signed URLs) |

---

*Last updated: 2026-08-18. Re-run §11 verification after each phase.*

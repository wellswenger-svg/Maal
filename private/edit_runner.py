"""Shared Flux edit runner — Kontext ReferenceLatent when bound, else Dev img2img."""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from PIL import Image

from backend.ai_engine.workflows._shared.profiles import (
    DENOISE_BY_PROFILE,
    MAX_SIDE_BY_PROFILE,
    standard_edit_profiles,
)
from backend.comfy_client import ComfyClient
from backend.config import Settings
from backend.workflows_wan import (
    CONTROLNET_FILES,
    KONTEXT_UNET,
    LORA_FILES,
    resolve_lora_stack,
)

_KONTEXT_LICENSE_WARN = "license_gate:flux_kontext_nc_verify_commercial_use"
_DEGRADED_WARN = "degraded:flux_dev_img2img_kontext_missing"

_NSFW_HINT = re.compile(
    r"\b(nude|naked|topless|undress|strip|nsfw|nipples?|"
    r"remove\s+(the\s+)?(top|shirt|clothes|clothing|bra)|"
    r"cumshot|cum\b|semen|cleavage|breasts?|boobs?|ass\b|booty)\b",
    re.I,
)
# Only true undress intents — bare "boobs/ass" must NOT trigger clothes_remover
_UNDRESS_HINT = re.compile(
    r"\b(nude|naked|topless|bottomless|undress|strip(ped)?|"
    r"no\s+clothes|without\s+clothes|"
    r"remove\s+(the\s+)?(top|shirt|clothes|clothing|bra)|"
    r"(expose|exposing|show|showing)\s+(her|his|their|the)?\s*"
    r"(nipples?|breasts?|boobs?|tits?|chest)|"
    r"fully\s+(nude|naked|exposed))\b",
    re.I,
)
_FLUID_HINT = re.compile(
    r"\b(cumshot|cum\b|semen|ejaculat\w*|facial\s+(cum|splash|shot)|"
    r"splooge|spooge|jizz|spunk)\b",
    re.I,
)
_CLOTHED_ENHANCE_HINT = re.compile(
    r"\b((bigger|larger|fuller|huge|enhance[d]?|enlarg(e|ed))\b.{0,40}\b"
    r"(breasts?|boobs?|tits?|cleavage|bust|ass|butts?|booty|hips|curves?)|"
    r"(breasts?|boobs?|tits?|cleavage|bust|ass|butts?|booty|hips|curves?)\b.{0,40}\b"
    r"(bigger|larger|fuller|huge|enhance[d]?|enlarg(e|ed)|size)|"
    r"clothed_enhance|keep\s+(the\s+)?clothes?\s+on)\b",
    re.I,
)
_BUST_HINT = re.compile(r"\b(breasts?|boobs?|tits?|cleavage|bust)\b", re.I)
_ASS_HINT = re.compile(
    r"\b(ass|butts?|booty|hips|glutes?|thighs?)\b", re.I
)
_DO_NOT_CHANGE_SPAN = re.compile(
    r"\b(do\s+not|don'?t)\s+change\s+(her\s+)?[^.]{0,40}",
    re.I,
)
_POSE_REAR_HINT = re.compile(
    r"\b("
    r"all\s+fours|on\s+all\s+fours|hands?\s+and\s+knees|"
    r"bent\s+over|bend(ing)?\s+over|ass\s+up|"
    r"rear\s+view|from\s+behind\s+pose|doggy\s*style\s*pose|"
    r"on\s+her\s+hands\s+and\s+knees"
    r")\b",
    re.I,
)
_WET_SHEER_HINT = re.compile(
    r"\b("
    r"see[\s-]?through|sheer|"
    r"wet\s+(shirt|top|tee|t[\s-]?shirt|blouse|fabric|clothes|clothing)|"
    r"(shirt|top|tee|t[\s-]?shirt|blouse)\s+(is\s+)?(wet|soaked|drenched|clingy)|"
    r"soaked\s+(shirt|top|tee|t[\s-]?shirt|blouse|fabric)|"
    r"clingy\s+(wet\s+)?(shirt|top|fabric)|"
    r"wet\s+look|transparent\s+(shirt|top|fabric)"
    r")\b",
    re.I,
)
# "no sheer fabric" must not load the see-through LoRA.
_NEGATED_SHEER = re.compile(
    r"\b(?:no|not|without|don'?t)\s+(?:see[\s-]?through|sheer|transparent)(?:\s+\w+)?",
    re.I,
)

# Stronger denoise when clothing/object edits fall back to Flux Dev img2img.
_DENOISE_DEGRADED: dict[str, float] = {
    "draft": 0.58,
    "balanced": 0.72,
    "quality": 0.78,
    "ultra": 0.85,
}


def _wants_wet_sheer(prompt: str, params: dict | None = None) -> bool:
    if params and bool(params.get("wet_sheer")):
        return True
    text = _NEGATED_SHEER.sub(" ", prompt or "")
    return bool(_WET_SHEER_HINT.search(text))


def _lora_on_disk(filename: str) -> bool:
    try:
        from backend.ai_engine.models.catalog import _find_weight

        return _find_weight(filename) is not None
    except Exception:
        # Fallback: shared + local model folders
        cands = [
            Path(r"E:\Comfy-Desktop\ComfyUI-Shared\models\loras") / filename,
            Path(r"E:\Comfy-Desktop\ComfyUI-Shared\models\controlnet") / filename,
        ]
        try:
            from backend.config import get_settings

            cdir = (get_settings().comfyui_dir or "").strip()
            if cdir:
                cands.append(Path(cdir) / "models" / "loras" / filename)
                cands.append(Path(cdir) / "models" / "controlnet" / filename)
        except Exception:
            pass
        return any(p.is_file() and p.stat().st_size > 1_000_000 for p in cands)


def _lora_available(filename: str) -> bool:
    """True if weight is on API disk, marked installed via Comfy refresh, or remote-only."""
    if _lora_on_disk(filename):
        return True
    try:
        from backend.ai_engine.models.manager import manager

        for rec in manager.all_models():
            if rec.filename == filename and rec.status in ("installed", "outdated"):
                return True
    except Exception:
        pass
    # Render/API has no COMFYUI_DIR — weights live on the GPU box behind the tunnel.
    # Trust known LoRA filenames; ComfyUI errors if a file is actually absent.
    try:
        from backend.ai_engine.models.catalog import _comfy_model_roots

        if not _comfy_model_roots() and filename in set(LORA_FILES.values()):
            return True
    except Exception:
        pass
    return False


def _refresh_lora_map() -> dict[str, str]:
    """Always merge private/lora_files into workflows_wan (avoids empty stack on import order)."""
    from backend.ai_engine.runtime_overlay import load_private_module
    from backend import workflows_wan as ww

    overlay = load_private_module("lora_files")
    if overlay is not None:
        ww.LORA_FILES.update(getattr(overlay, "LORA_FILES", {}) or {})
        ww.LORA_DEFAULT_STRENGTH.update(
            getattr(overlay, "LORA_DEFAULT_STRENGTH", {}) or {}
        )
    return ww.LORA_FILES


def _select_loras(
    *,
    plan: Any,
    user_prompt: str,
    use_kontext: bool,
) -> list[tuple[str, float, float]]:
    """Pick LoRAs for NSFW/undress/fluid/clothed enhance; remote Comfy OK."""
    from backend import workflows_wan as ww

    lora_files = _refresh_lora_map()
    params = getattr(plan, "params_hints", None) or {} if plan else {}
    ids = list(params.get("loras") or [])
    prompt = user_prompt or ""
    fluid = bool(params.get("fluid_edit")) or bool(_FLUID_HINT.search(prompt))
    undress_fluid = bool(params.get("undress_fluid"))
    pose_edit = bool(params.get("pose_edit")) or bool(_POSE_REAR_HINT.search(prompt))
    pose_undress = bool(params.get("pose_undress"))
    wet_sheer = _wants_wet_sheer(prompt, params)
    clothed = bool(params.get("clothed_enhance")) or bool(
        _CLOTHED_ENHANCE_HINT.search(prompt)
    )
    undress = (not fluid or undress_fluid or pose_undress) and (not clothed) and (
        not wet_sheer
    ) and (
        "clothes_remover" in ids
        or undress_fluid
        or pose_undress
        or bool(_UNDRESS_HINT.search(prompt))
    )
    # Clothed pose / wet sheer must never keep clothes_remover
    if (pose_edit and not pose_undress) or wet_sheer:
        undress = False
    nsfw = (
        bool(params.get("nsfw_edit"))
        or fluid
        or clothed
        or undress
        or pose_edit
        or wet_sheer
        or bool(_NSFW_HINT.search(prompt))
        or bool(_FLUID_HINT.search(prompt))
    )
    if not ids and nsfw:
        if (undress or undress_fluid or pose_undress) and use_kontext:
            ids = ["clothes_remover", "nsfw_unlock"]
        else:
            ids = ["nsfw_unlock"]
    # Body fluid + undress / nude pose: keep clothes_remover
    if undress_fluid or pose_undress:
        ids = [x for x in ids if x != "clothes_remover"]
        ids = ["clothes_remover", *ids]
        if "nsfw_unlock" not in ids:
            ids.append("nsfw_unlock")
        if "cof" not in ids:
            ids.append("cof")
    # Face-only fluid / clothed size-up / clothed pose / wet sheer
    elif fluid or clothed or wet_sheer or (pose_edit and not pose_undress):
        ids = [x for x in ids if x != "clothes_remover"]
        if "nsfw_unlock" not in ids:
            ids.append("nsfw_unlock")
        # Mild COF helps slimy ropes; high weights → opaque paint mask.
        if fluid and not undress_fluid and "cof" not in ids:
            ids.append("cof")
        if wet_sheer:
            if "see_through" not in ids:
                ids.append("see_through")
            if "wet_shirt" not in ids:
                ids.append("wet_shirt")
    # Kontext undress: clothes_remover first, then unlock
    elif use_kontext and undress and "clothes_remover" not in ids:
        ids = ["clothes_remover", *[x for x in ids if x != "clothes_remover"]]
    if clothed:
        labels = {
            str(t.get("label") or "")
            for t in (getattr(plan, "targets", None) or [])
            if isinstance(t, dict)
        }
        scrubbed = _DO_NOT_CHANGE_SPAN.sub(" ", prompt)
        want_bust = bool(labels & {"cleavage", "breasts", "curves"}) or (
            not labels and bool(_BUST_HINT.search(scrubbed))
        )
        want_hip = bool(labels & {"ass", "curves"}) or bool(_ASS_HINT.search(scrubbed))
        if "breast_enhance" not in ids and want_bust:
            ids.append("breast_enhance")
        if "ass_enhance" not in ids and want_hip:
            ids.append("ass_enhance")
    kept: list[str] = []
    missing: list[str] = []
    for lid in ids:
        fn = lora_files.get(lid, lid if str(lid).endswith(".safetensors") else None)
        if fn and _lora_available(fn):
            kept.append(lid)
        elif lid:
            missing.append(str(lid))
    strengths = None
    if nsfw:
        unlock_w = (
            1.05
            if wet_sheer
            else (
                0.95
                if (fluid or clothed or undress_fluid or pose_edit)
                else 0.90
            )
        )
        remover_w = 0.98 if (undress_fluid or pose_undress) else 0.95
        strengths = {
            "clothes_remover": remover_w,
            "nsfw_unlock": unlock_w,
            # Mild COF for face fluid (slimy ropes); high → opaque paint.
            "cof": 0.95 if undress_fluid else 0.58,
            "see_through": 0.90,
            "wet_shirt": 0.88,
            "breast_enhance": float(
                __import__("os").environ.get("KEEP_OUTFIT_BREAST_STRENGTH", "0.82")
                or 0.82
            ),
            "ass_enhance": float(
                __import__("os").environ.get("KEEP_OUTFIT_ASS_STRENGTH", "0.82")
                or 0.82
            ),
            "hip_enhance": float(
                __import__("os").environ.get("KEEP_OUTFIT_ASS_STRENGTH", "0.82")
                or 0.82
            ),
        }
    stack = ww.resolve_lora_stack(kept, strengths=strengths)
    # Stash miss list on the function for run_flux_edit tags (avoid silent empty stack).
    _select_loras._last_missing = missing  # type: ignore[attr-defined]
    return stack


def _controlnet_available(filename: str) -> bool:
    if _lora_on_disk(filename):
        return True
    try:
        from backend.ai_engine.models.manager import manager

        for rec in manager.all_models():
            if rec.filename == filename and rec.status in ("installed", "outdated"):
                return True
    except Exception:
        pass
    try:
        from backend.ai_engine.models.catalog import _comfy_model_roots

        # Remote GPU: trust known ControlNet filenames (same as LoRAs).
        if not _comfy_model_roots() and filename in set(CONTROLNET_FILES.values()):
            return True
    except Exception:
        pass
    return False


def _resolve_controlnet_name() -> Optional[str]:
    for fn in CONTROLNET_FILES.values():
        if _controlnet_available(fn):
            return fn
    return None


def _pose_all_fours_template_bytes() -> Optional[bytes]:
    """OpenPose-style all-fours stick figure used as ControlNet target (not source pose)."""
    path = Path(__file__).resolve().parents[3] / "assets" / "pose_all_fours_openpose.png"
    try:
        if path.is_file() and path.stat().st_size > 100:
            return path.read_bytes()
    except OSError:
        pass
    try:
        from io import BytesIO

        from PIL import Image, ImageDraw

        w, h = 768, 768
        img = Image.new("RGB", (w, h), (0, 0, 0))
        d = ImageDraw.Draw(img)

        def limb(a, b, color, width=14):
            d.line([a, b], fill=color, width=width)

        def joint(p, color=(255, 255, 255), r=10):
            d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=color)

        nose, neck = (220, 260), (280, 300)
        lsho, rsho = (250, 320), (310, 320)
        lel, rel = (200, 380), (200, 400)
        lwr, rwr = (160, 460), (170, 480)
        lhip, rhip = (420, 340), (450, 360)
        lknee, rknee = (520, 420), (540, 450)
        lank, rank = (600, 500), (620, 530)
        limb(neck, lhip, (0, 255, 0))
        limb(neck, rhip, (0, 200, 0))
        limb(lsho, rsho, (255, 0, 0))
        limb(lsho, lel, (255, 85, 0))
        limb(lel, lwr, (255, 170, 0))
        limb(rsho, rel, (255, 255, 0))
        limb(rel, rwr, (170, 255, 0))
        limb(lhip, lknee, (0, 255, 255))
        limb(lknee, lank, (0, 170, 255))
        limb(rhip, rknee, (85, 0, 255))
        limb(rknee, rank, (255, 0, 255))
        limb(nose, neck, (255, 0, 85))
        for p in (
            nose,
            neck,
            lsho,
            rsho,
            lel,
            rel,
            lwr,
            rwr,
            lhip,
            rhip,
            lknee,
            rknee,
            lank,
            rank,
        ):
            joint(p)
        buf = BytesIO()
        img.save(buf, format="PNG")
        data = buf.getvalue()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except OSError:
            pass
        return data
    except Exception:
        return None


def _profile_name(plan: Any, profile: Any) -> str:
    if isinstance(profile, str) and profile:
        return profile
    if plan is not None and getattr(plan, "profile", None):
        return str(plan.profile)
    return "balanced"


def _preferred_wants_kontext(workflow: Any) -> bool:
    prefs = getattr(workflow, "preferred_models", None) or []
    return any("kontext" in str(p).lower() for p in prefs)


def _is_kontext_backbone(backbone: Any) -> bool:
    if backbone is None:
        return False
    mid = str(getattr(backbone, "model_id", "") or "").lower()
    fn = str(getattr(backbone, "filename", "") or "").lower()
    return "kontext" in mid or "kontext" in fn


def build_edit_prompt(
    *,
    user_prompt: str,
    task_kind: str,
    targets: list[dict[str, Any]] | None = None,
    mask_failed: bool = False,
    for_kontext: bool = False,
    degraded_dev: bool = False,
    raw_prompt: bool = True,
    face_view: str | None = None,
) -> str:
    """Task-specific instruction wrappers. Raw mode passes user text with light hints."""
    edit = (user_prompt or "").strip()
    labels = [
        str(t.get("label") or t.get("phrase") or "").strip()
        for t in (targets or [])
        if isinstance(t, dict)
    ]
    labels = [x for x in labels if x]
    focus = ", ".join(labels[:4])

    if raw_prompt or for_kontext:
        # User text first — models follow better without preserve/identity lockrails.
        if focus and task_kind in ("clothing", "object", "remove", "add", "face", "hair"):
            body = f"{edit}. Focus: {focus}".strip(" .")
        else:
            body = edit or "Edit the image as requested."
        if degraded_dev and task_kind in ("clothing", "object", "hair", "background"):
            body = f"{body}. Make the requested change clearly visible."
        # Fluid overlays: force identity lock even in raw mode (otherwise face morphs).
        if _FLUID_HINT.search(edit):
            if _UNDRESS_HINT.search(edit) and not re.search(
                r"\b(do\s+not\s+undress|don'?t\s+undress|keep\s+(her\s+)?clothes)\b",
                edit,
                re.I,
            ):
                body = (
                    f"{body} "
                    f"CRITICAL identity lock: keep the exact same woman — same face geometry, "
                    f"eyes, eyebrows, nose, lip shape, skin tone, age, and hairline. "
                    f"Remove all clothing so she is fully nude, then add realistic semen: "
                    f"whitish translucent cum is splattered — cream-grey opalescent gooey "
                    f"stringy wet fluid, not opaque white. Irregular glossy droplets, gel "
                    f"beads, and watery drips of uneven thickness across face, neck, breasts, "
                    f"stomach, and thighs; skin remains visible through thinner films; "
                    f"never a uniform sheet. "
                    f"Not white paint, not a solid opaque coat, not makeup. "
                    f"Do not remake, beautify, or replace her face."
                )
            else:
                focus_l = (focus or "face").lower()
                if focus_l in ("face", "facial"):
                    fluid_bit = (
                        "slimy translucent whitish semen on her face — denser cream-white "
                        "gooey stringy wet gel in uneven ropes on forehead, eyelids, cheeks, "
                        "nose, lips, and chin with sticky drips hanging from nose and chin, plus "
                        "natural uneven drips on chest/clothes. On hair: keep her exact rich dark "
                        "hair color (do not dull, gray, bleach, or desaturate it) and add only "
                        "inconsistent small amounts of slimy semen in one crown/hairline patch — "
                        "scattered beads and thin wet films so local strands look wet/slimy with "
                        "real hair color showing between drips. Never a gray wash or white blob on "
                        "hair, never melted hair. CRITICAL: mostly translucent so skin, eyes, and cheeks "
                        "clearly show through on thin films, but thicker ropes/beads/drips stay "
                        "milky cream-white and clearly visible with wet speculars. Soft wet edges — no "
                        "cartoon outline, no sticker rim, no blue fringe, no gray digital outline, "
                        "no wispy smoke. "
                        "Never flat matte opaque white paint covering the midface, "
                        "acrylic, chalk, or toothpaste."
                    )
                elif focus_l in ("lips", "mouth"):
                    fluid_bit = (
                        "a little whitish translucent cum splattered on the lips only — "
                        "shallow cream-grey opalescent gooey droplets, thin film, lip "
                        "color still visible. Sparse, uneven beads, not a uniform blob "
                        "covering the mouth."
                    )
                elif focus_l in ("glasses", "lenses"):
                    fluid_bit = (
                        "one or two shallow whitish translucent cum drips on the "
                        "glasses/lenses only; glass still readable through the cream-grey "
                        "opalescent film. Not opaque blobs."
                    )
                else:
                    fluid_bit = (
                        f"sparse whitish translucent cum splattered on the {focus}: a few "
                        f"shallow cream-grey opalescent droplets and thin watery streaks, "
                        f"skin still visible through the film, uneven not a uniform coat."
                    )
                body = (
                    f"{body} "
                    f"CRITICAL identity lock: keep the exact same woman — same face geometry, "
                    f"eyes, eyebrows, nose, lip shape, skin tone, age, hairline, and expression. "
                    f"Only add {fluid_bit} "
                    f"Not paint, not makeup, not a white mask. "
                    f"Do not remake, beautify, age, or replace her face or body. Keep her clothes on."
                )
        # Rear pose change (clothed or nude)
        elif _POSE_REAR_HINT.search(edit):
            nude_pose = _UNDRESS_HINT.search(edit) and not re.search(
                r"\b(do\s+not\s+undress|don'?t\s+undress|keep\s+(her\s+)?clothes)\b",
                edit,
                re.I,
            )
            view = (face_view or "full").lower()
            if view == "profile":
                cam = (
                    "Camera stays a side / three-quarter view matching the start image — "
                    "that much of her face stays visible and sharp while she is on all fours. "
                    "Do not invent a new frontal face. Do not hide the visible face. "
                    "Do not show only the back of her head."
                )
            else:
                cam = (
                    "Full-body 3/4 side camera: she is on all fours and looks back over "
                    "her shoulder so her face stays in frame, sharp and recognizable. "
                    "Do not crop to a seated portrait. Do not hide her face. "
                    "Do not show only the back of her head."
                )
            pose_bit = (
                "REQUIRED pose: on all fours — both palms flat on the floor and both "
                "knees on the floor, four points of contact, torso roughly parallel to "
                "the ground, hips raised, ass up, arms supporting her upper body, "
                "full body in frame. "
            )
            body_lock = (
                "Keep her exact start-image body: same height, weight, limb length, "
                "breast and hip shape, skin, and hair. Natural anatomy, no extra limbs, "
                "no melted torso."
            )
            if nude_pose:
                body = (
                    f"{body} "
                    f"CRITICAL identity lock: keep the exact same woman — same face geometry, "
                    f"eyes, eyebrows, nose, lips, jaw, skin tone, age, and hair. "
                    f"Remove all clothing so she is fully nude. "
                    f"{pose_bit}{cam} {body_lock} "
                    f"Same background. Do not remake or replace her face."
                )
            else:
                body = (
                    f"{body} "
                    f"CRITICAL: keep ALL clothing fully on — same outfit, fabric, color, "
                    f"and coverage (including shorts if she wears them). "
                    f"Keep the exact same face, hair, and identity. "
                    f"{pose_bit}{cam} {body_lock} "
                    f"Same background. Do not undress."
                )
        # Wet / see-through shirt: garment stays on, fabric turns sheer
        elif _wants_wet_sheer(edit):
            body = (
                f"{body} "
                f"Keep the SAME shirt/top — same color, same cut, same neckline, same sleeves, "
                f"same fabric type. Do not change it into a different outfit. "
                f"REQUIRED: wet clothes, see through clothes, transparent clothes. Soak THIS "
                f"garment until it clings, shiny water highlights, fabric turned translucent "
                f"so breast shape and nipples clearly show through. "
                f"Do not output the original dry clothes. Do not make the cloth opaque. "
                f"Keep the garment ON — do not remove it, do not make her fully nude. "
                f"Keep the exact same face, hair, pose, framing, and background."
            )
        # Clothed body size-up: keep outfit on; only reshape curves under fabric.
        elif _CLOTHED_ENHANCE_HINT.search(edit) or task_kind == "keep_outfit":
            focus_bit = focus or "curves"
            body = (
                f"{body} "
                f"Keep ALL clothing on — same garment type and color as the start image. "
                f"Do not undress or invent a new outfit. "
                f"Only change volume under the cloth for {focus_bit}. "
                f"Fabric may drape and fill as the body shape changes; keep straps and hem "
                f"in place. Keep the cloth opaque and covering. "
                f"Keep the same objects in her hands. "
                f"Keep the exact same face, hair, pose, framing, and background."
            )
        return body

    templates = {
        "keep_outfit": (
            "Keep the same person and the same garment type and color. "
            "Only change body volume under the cloth; fabric may drape. "
            f"Request: {edit}"
        ),
        "instruction": (
            "Apply this edit instruction precisely while preserving identity and scene: "
            f"{edit}"
        ),
        "clothing": (
            "Replace or recolor only the garment region"
            + (f" ({focus})" if focus else "")
            + f". Keep face, body, pose, and background unchanged. Request: {edit}"
        ),
        "object": (
            "Edit only the named object(s)"
            + (f" ({focus})" if focus else "")
            + f". Preserve everything else. Request: {edit}"
        ),
        "remove": (
            "Remove the target object"
            + (f" ({focus})" if focus else "")
            + " and fill naturally with surrounding background. "
            f"Request: {edit}"
        ),
        "add": (
            "Add the requested object into the scene naturally"
            + (f" near {focus}" if focus else "")
            + f". Preserve existing subjects. Request: {edit}"
        ),
        "inpaint": f"Inpaint the masked/target region only. Request: {edit}",
        "outpaint": f"Extend the canvas / outpaint seamlessly. Request: {edit}",
        "face": (
            "Edit facial expression/features only; keep identity, hair, body, and "
            f"background unchanged. Request: {edit}"
        ),
        "hair": (
            "Edit hair only (style/color/length); keep face identity and clothing "
            f"unchanged. Request: {edit}"
        ),
        "background": (
            "Replace only the background; keep the subject sharp and unchanged. "
            f"Request: {edit}"
        ),
        "product": (
            "Product/studio cleanup: isolate subject, improve presentation, "
            f"keep product identity. Request: {edit}"
        ),
        "style": f"Apply global style transfer while keeping composition. Request: {edit}",
        "identity": f"Preserve character identity strongly while applying: {edit}",
        "face_swap": f"Face swap / identity transfer as requested. Request: {edit}",
        "restore": (
            "Restore and enhance photo quality (denoise, sharpen faces gently). "
            f"Request: {edit or 'restore photo'}"
        ),
        "upscale": (
            "Upscale and enhance fine detail without changing content. "
            f"Request: {edit or 'upscale'}"
        ),
    }
    body = templates.get(task_kind, templates["instruction"])
    if degraded_dev and task_kind in ("clothing", "object", "hair", "background"):
        body = (
            "IMPORTANT: the requested change must be clearly visible in the output. "
            + body
        )
    if mask_failed:
        body = (
            "[mask_failed] Use instruction-only edit; do not invent a new person. "
            + body
        )
    return body


def pad_for_outpaint(image_bytes: bytes, pad_ratio: float = 0.15) -> bytes:
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    pad_x, pad_y = max(16, int(w * pad_ratio)), max(16, int(h * pad_ratio))
    canvas = Image.new("RGB", (w + 2 * pad_x, h + 2 * pad_y), (127, 127, 127))
    canvas.paste(img, (pad_x, pad_y))
    buf = BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def simple_upscale(image_bytes: bytes, scale: float = 2.0) -> bytes:
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    nw, nh = max(1, int(img.width * scale)), max(1, int(img.height * scale))
    out = img.resize((nw, nh), Image.Resampling.LANCZOS)
    buf = BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


async def run_flux_edit(
    *,
    image_bytes: bytes,
    prompt: str,
    negative: Optional[str],
    seed: Optional[int],
    settings: Settings,
    plan: Any = None,
    backbone: Any = None,
    profile: Any = None,
    perception: Any = None,
    workflow: Any = None,
    task_kind: str = "instruction",
    denoise_override: Optional[float] = None,
    preprocess: Optional[str] = None,
    **_: Any,
) -> tuple[bytes, str, str, str]:
    """
    Execute edit via Flux Kontext (ReferenceLatent) when bound, else Flux Dev img2img.
    """
    pname = _profile_name(plan, profile)
    params = getattr(plan, "params_hints", None) or {}

    qp = None
    if workflow is not None:
        qp = (workflow.quality_profiles or {}).get(pname)
    if qp is None:
        qp = standard_edit_profiles().get(pname)

    steps = int(params.get("steps") or (qp.steps if qp else 28))
    denoise = denoise_override
    raw = bool(getattr(settings, "raw_prompt", True))
    fluid = bool(params.get("fluid_edit")) or bool(_FLUID_HINT.search((prompt or "")))
    undress_fluid = bool(params.get("undress_fluid"))
    pose_edit = bool(params.get("pose_edit")) or bool(_POSE_REAR_HINT.search((prompt or "")))
    pose_undress = bool(params.get("pose_undress"))
    wet_sheer = _wants_wet_sheer(prompt or "", params)
    clothed = bool(params.get("clothed_enhance")) or bool(
        _CLOTHED_ENHANCE_HINT.search((prompt or ""))
    )
    keep_outfit = task_kind == "keep_outfit" or (
        clothed and not wet_sheer and not pose_edit
    )
    if keep_outfit:
        clothed = True
    if denoise is None:
        denoise = float(params.get("denoise") or DENOISE_BY_PROFILE.get(pname, 0.55))
    # Raw mode often raises denoise for stronger edits — skip that for face-only fluid.
    if raw and not fluid and not keep_outfit:
        denoise = max(denoise, float(getattr(settings, "image_denoise", 0.55) or 0.55))
    if raw and undress_fluid:
        denoise = max(float(denoise), 0.88)
    if raw and pose_edit:
        denoise = max(float(denoise), 0.88 if pose_undress else 0.84)
    if raw and wet_sheer:
        denoise = max(float(denoise), 0.86)
    if raw and clothed and not keep_outfit:
        denoise = max(float(denoise), 0.80)
    max_side = int(params.get("max_side") or MAX_SIDE_BY_PROFILE.get(pname, 1024))

    mask_failed = False
    extra_tags: list[str] = []
    if perception is not None:
        pw = getattr(perception, "warnings", None) or []
        if "mask_failed" in pw or "perception_degraded" in pw:
            mask_failed = True
            extra_tags.append("mask_failed")

    use_kontext = _is_kontext_backbone(backbone)
    nsfw_flag = bool(params.get("nsfw_edit")) or bool(
        _NSFW_HINT.search((prompt or ""))
    ) or fluid or clothed or undress_fluid or pose_edit or wet_sheer
    # Soft-refusal on stock Dev is common without NSFW unlock.
    # Force Kontext for NSFW/wet/pose when the weight may live on the GPU box
    # even if the API catalog still says missing (Render has no local COMFYUI_DIR).
    controlnet_name = _resolve_controlnet_name() if pose_edit else None
    pose_control_bytes = _pose_all_fours_template_bytes() if pose_edit else None
    use_pose_control = bool(pose_edit and controlnet_name and pose_control_bytes)
    flux_unet_forced: Optional[str] = None
    if (
        nsfw_flag or fluid or clothed or undress_fluid or pose_edit or wet_sheer
    ) and not use_kontext and not keep_outfit:
        try:
            from backend.ai_engine.models.manager import manager as _mm

            krec = _mm.get("backbone.flux_kontext_dev_fp8")
            if krec and krec.status in ("installed", "outdated") and krec.filename:
                use_kontext = True
                backbone = krec
            else:
                # Assume remote Comfy shared models include Kontext (already on disk).
                use_kontext = True
                flux_unet_forced = KONTEXT_UNET
        except Exception:
            use_kontext = True
            flux_unet_forced = KONTEXT_UNET
    # Pose + ControlNet works best as Dev/Kontext *img2img* (not ReferenceLatent denoise=1).
    # Keep identity via latent + drive all-fours via target OpenPose map.
    if use_pose_control:
        use_kontext = False
        extra_tags.append("pose_controlnet")
    elif keep_outfit:
        import os as _os

        # Optional: force masked Dev/Kontext *img2img* for hard layered tops.
        if (_os.environ.get("KEEP_OUTFIT_FORCE_I2I") or "").strip() in (
            "1",
            "true",
            "yes",
        ):
            use_kontext = False
            extra_tags.append("keep_outfit_i2i")
            if not flux_unet_forced:
                flux_unet_forced = KONTEXT_UNET
        else:
            # Bigger breasts/butts LoRA is Flux-Kontext native — ReferenceLatent
            # follows the instruction + LoRA better than low-denoise i2i.
            use_kontext = True
            extra_tags.append("keep_outfit_kontext")
            if not flux_unet_forced:
                flux_unet_forced = KONTEXT_UNET
    elif clothed and not wet_sheer:
        # Non-keep clothed size-up still uses masked i2i.
        use_kontext = False
        extra_tags.append("clothed_i2i")
        if not flux_unet_forced:
            flux_unet_forced = KONTEXT_UNET
    degraded = (
        (not use_kontext)
        and _preferred_wants_kontext(workflow)
        and not use_pose_control
        and "clothed_i2i" not in extra_tags
        and "keep_outfit_i2i" not in extra_tags
    )
    if degraded:
        extra_tags.append(_DEGRADED_WARN)
        if (
            task_kind in ("clothing", "object", "hair", "background", "instruction")
            and not fluid
        ):
            denoise = max(denoise, _DENOISE_DEGRADED.get(pname, 0.72))
    # Cap Dev img2img strength for face-only fluid so identity survives the fallback path
    if fluid and not undress_fluid and not use_kontext:
        denoise = min(float(denoise), 0.72)
        extra_tags.append("fluid_identity_cap")
    if undress_fluid and not use_kontext:
        denoise = min(max(float(denoise), 0.88), 0.95)
        extra_tags.append("undress_fluid_cap")
    if pose_edit and not use_kontext and not use_pose_control:
        if pose_undress:
            denoise = min(max(float(denoise), 0.84), 0.90)
        else:
            denoise = min(max(float(denoise), 0.78), 0.86)
        extra_tags.append("pose_edit_cap")
    if use_pose_control:
        # High denoise so ControlNet pose can reshape; identity from start latent.
        denoise = min(max(float(denoise), 0.86), 0.92)
    if wet_sheer and not use_kontext:
        denoise = min(max(float(denoise), 0.84), 0.92)
        extra_tags.append("wet_sheer_cap")
    # Clothed enhance: chest-only noise mask. Volume + tighter cloth need room
    # above 0.70; face/hands are restored in post.
    if keep_outfit and not use_kontext:
        denoise = min(max(float(denoise_override or denoise or 0.80), 0.76), 0.86)
        extra_tags.append("keep_outfit_reshape_cap")
    elif clothed and not use_kontext:
        denoise = min(max(float(denoise), 0.80), 0.86)
        extra_tags.append("clothed_enhance_cap")

    _FLUID_NEG = (
        "different person, face swap, changed identity, wrong face, morphing face, "
        "identity drift, beautified face, different eyes, different nose, "
        "different jaw, age change, face reshape, face hidden, face erased, "
        "matte white paint, acrylic paint, gouache, flat opaque white patch, "
        "solid white mask, plaster, chalk, toothpaste, whiteout, primer, "
        "opaque coating hiding skin, face covered in solid white, "
        "flat gray digital streaks, gray glitch overlay, smoke wisps, blue hair dye, "
        "blue fringe, blue outline, cyan wisps, gray digital outline, "
        "hair-like smoke streaks, neon edge artifacts, "
        "melted hair, fried hair, smudged hair, plastic hair, hair smear, "
        "hair replaced by white paint, white hair blob, gray digital hair, "
        "blue hair streaks, hair texture gone, dulled hair, desaturated hair, "
        "gray hair wash, faded hair color, flat matte hair overlay, "
        "cartoon cum, sticker overlay, glowing outline, neon rim, comic paint, "
        "vector splash, flat cel shading, digital brush stroke outline"
    )
    _CLOTHED_NEG = (
        "nude, naked, topless, bottomless, undress, no clothes, removed clothes, "
        "bare breasts, exposed breasts, breasts outside clothes, "
        "exposed nipples, nipples visible, nipple outline, areola, "
        "nipple poke, poking nipples, hard nipples through fabric, "
        "breasts popping out, spilling out of clothes, "
        "breasts resting on top of the shirt, breasts above the neckline, "
        "breasts sitting on the collar, pulled-down neckline, shirt too short, "
        "chest cutouts, boob windows, underboob cutout, sideboob hole, "
        "incomplete clothes, "
        "frayed hem, unfinished shirt, different neckline, "
        "lingerie only, see-through clothes, translucent shirt, poke-through nipples, "
        "wet clingy nipples, "
        "flat chest, small bust, no cleavage, unchanged chest, loose baggy top, "
        "recolored shirt, different colored top, "
        "nipple outline, areola through clothes, see-through knit, hard vertical cleavage slit, "
        "warped torso, melted fabric, smeared hands, faded hands, blurry fingers, "
        "blob chest, extra breasts, yellow stain, color flare, burned highlight, "
        "smeared shirt, warped background, melted fence, extra people, "
        "deformed anatomy, stretched ribs, duplicated body, melted armpit, "
        "different person, face swap, changed identity, wrong face, "
        "different outfit, cardigan, clothing swap"
    )
    _WET_SHEER_NEG = (
        "dry shirt, dry clothes, original dry fabric, unchanged clothes, "
        "opaque dry cotton, opaque wet fabric, black dress, cocktail dress, "
        "evening gown, little black dress, latex dress, leather dress, new outfit, "
        "clothing swap, different clothes, dress instead of shirt, "
        "fully nude, naked, removed shirt, no clothes, undress, "
        "clothes removed, bare chest without fabric, different person, face swap, "
        "changed identity, wrong face"
    )
    _POSE_NEG = (
        "different person, face swap, changed identity, wrong face, morphing face, "
        "identity drift, different woman, extra people, man in frame, "
        "face hidden, face away from camera, back of head only, faceless, "
        "rear view hiding face, extra limbs, melted body, extra arms, extra legs, "
        "wrong body proportions, different body, "
        "sitting, sitting on heels, sitting on legs, sitting on calves, seiza, "
        "kneeling upright, sitting back, crouching sit, yoga sit, seated portrait, "
        "upright torso, sitting on the floor"
    )
    if fluid:
        negative = ", ".join(
            x for x in ((negative or "").strip(), _FLUID_NEG) if x
        )
    elif wet_sheer:
        negative = ", ".join(
            x for x in ((negative or "").strip(), _WET_SHEER_NEG) if x
        )
    elif pose_edit and not pose_undress:
        negative = ", ".join(
            x for x in ((negative or "").strip(), _CLOTHED_NEG, _POSE_NEG) if x
        )
    elif pose_edit:
        negative = ", ".join(
            x for x in ((negative or "").strip(), _POSE_NEG) if x
        )
    elif clothed:
        negative = ", ".join(
            x for x in ((negative or "").strip(), _CLOTHED_NEG) if x
        )

    targets = getattr(plan, "targets", None) if plan else None
    user_prompt = prompt
    if plan and getattr(plan, "prompts", None):
        # Prefer original user english over VLM rewrites when raw
        if raw and getattr(plan, "prompts", None).get("user"):
            user_prompt = (
                plan.prompts.get("user") or plan.prompts.get("positive") or prompt or ""
            ).strip()
        else:
            user_prompt = (plan.prompts.get("positive") or prompt or "").strip()

    face_view = None
    if pose_edit:
        try:
            from backend.ai_engine.perception.face_view import classify_face_view

            face_view = classify_face_view(image_bytes)
            extra_tags.append(f"face_view:{face_view}")
        except Exception:
            face_view = "full"
    final_prompt = build_edit_prompt(
        user_prompt=user_prompt,
        task_kind=task_kind,
        targets=list(targets or []),
        mask_failed=mask_failed,
        for_kontext=use_kontext,
        degraded_dev=degraded,
        raw_prompt=raw,
        face_view=face_view,
    )
    if raw:
        extra_tags.append("raw_prompt")

    lora_stack = _select_loras(
        plan=plan, user_prompt=user_prompt, use_kontext=use_kontext
    )
    if lora_stack:
        names = "+".join(fn for fn, _, _ in lora_stack)
        extra_tags.append(f"loras:{names}")
        # Aidma unlock trigger helps Dev/CLIP path
        if any("aidma" in fn.lower() for fn, _, _ in lora_stack):
            if "aidmansfwunlock" not in final_prompt.lower():
                final_prompt = f"aidmaNSFWunlock. {final_prompt}"
        if any(
            (
                "Huge_natural_breasts" in fn
                or "kontext_big_breasts" in fn
                or "figure_reshape" in fn
                or "figure_volume" in fn
                or "BustyWomen" in fn
            )
            for fn, _, _ in lora_stack
        ):
            if "volume under cloth" not in final_prompt.lower():
                final_prompt = (
                    "same garment type and color, volume under cloth, fabric may drape, "
                    "shirt covering chest. "
                    + final_prompt
                )
        if any("clothes_remover" in fn.lower() for fn, _, _ in lora_stack):
            # Clothes-remover LoRA responds better with an explicit undress cue.
            low = final_prompt.lower()
            if not any(k in low for k in ("nude", "naked", "undress", "no clothes", "remove")):
                final_prompt = f"remove clothes, nude. {final_prompt}"
    else:
        missing = list(getattr(_select_loras, "_last_missing", []) or [])
        if keep_outfit or clothed:
            extra_tags.append(
                "loras_missing:" + ("+".join(missing) if missing else "empty_stack")
            )

    work_bytes = image_bytes
    if preprocess == "outpaint_pad":
        work_bytes = pad_for_outpaint(image_bytes)
    elif preprocess == "upscale_pre":
        if pname == "draft":
            data = simple_upscale(image_bytes, 2.0)
            return data, "image/png", "img", "upscale.lanczos"
        work_bytes = simple_upscale(image_bytes, 1.5)

    model_label = "backbone.flux_dev_fp8"
    flux_unet: Optional[str] = None
    if backbone is not None:
        model_label = getattr(backbone, "model_id", None) or model_label
        filename = getattr(backbone, "filename", None)
        if (
            filename
            and str(filename).endswith((".safetensors", ".gguf", ".ckpt"))
            and "fill" not in str(filename).lower()
            and str(model_label).startswith("backbone.")
        ):
            flux_unet = str(filename)
    if flux_unet_forced:
        flux_unet = flux_unet_forced
        model_label = "backbone.flux_kontext_dev_fp8"
    if use_pose_control and not flux_unet:
        # Prefer Kontext weights in img2img when available for better instruction follow.
        flux_unet = KONTEXT_UNET
        model_label = "backbone.flux_kontext_dev_fp8|img2img_pose"

    if use_kontext:
        extra_tags.append(_KONTEXT_LICENSE_WARN)

    denoise_cap = float(getattr(settings, "image_denoise_cap", 0.85) or 0.85)
    if degraded:
        denoise_cap = max(denoise_cap, 0.90)
    if wet_sheer:
        denoise_cap = max(denoise_cap, 0.92)
    if clothed:
        denoise_cap = max(denoise_cap, 0.90)
    if keep_outfit:
        denoise_cap = max(denoise_cap, 0.88)
    if use_pose_control:
        denoise_cap = max(denoise_cap, 0.92)

    client = ComfyClient(settings)
    if use_kontext:
        # Slightly higher guidance in raw mode for tighter instruction follow
        g = 3.0 if raw else 2.5
        if fluid:
            g = 3.4  # follow shallow/opalescent material, not a solid white fill
        if wet_sheer:
            g = 3.6  # LoRAs drive wet/sheer; high CFG was swapping in a black dress
        if pose_edit:
            g = 4.0  # full body pose change; 3.0 only kneel-sits
        if clothed or keep_outfit:
            g = 3.8  # strong size-up; face restored in post for keep_outfit
            if keep_outfit:
                import os as _os

                g_override = (_os.environ.get("KEEP_OUTFIT_GUIDANCE") or "").strip()
                if g_override:
                    try:
                        g = float(g_override)
                    except ValueError:
                        pass
        data, content_type = await client.generate_image(
            work_bytes,
            final_prompt,
            negative=negative,
            seed=seed,
            steps=steps,
            max_width=max_side,
            max_height=max_side,
            flux_unet=flux_unet,
            edit_graph="kontext",
            guidance=g,
            loras=lora_stack,
        )
        if keep_outfit and data:
            from backend.ai_engine.post.face_lock import restore_original_face

            # Kontext rewrites the full frame — do not soft-paste the start
            # torso (that caused ghosting). Only lock the face.
            data = restore_original_face(image_bytes, data)
            extra_tags.append("face_lock")
    else:
        g = None
        if use_pose_control:
            g = 4.0
        elif keep_outfit:
            g = 3.6
        elif clothed:
            g = 4.0
        mask_bytes = None
        wrap_mode: Optional[str] = None
        wrap_preserve = bool(fluid or clothed) and not use_pose_control and not keep_outfit
        if keep_outfit:
            wrap_mode = "fabric"
        pulid_file: Optional[str] = None
        source_bytes = work_bytes
        _garment_png = None
        _edit_mask_png = None
        if keep_outfit:
            pulid_file = "pulid_flux_v0.9.1.safetensors"
            identity_prompt = (
                "Photorealistic photograph of the same person. "
                "Keep face, hair, clothes, pose, lighting, and background. "
                "Subtle photoreal refine only."
            )
            identity_loras = [
                t
                for t in lora_stack
                if "Huge_natural" not in t[0]
                and "kontext_big_breasts" not in t[0]
                and "figure_reshape" not in t[0]
                and "figure_volume" not in t[0]
                and "figure_hip" not in t[0]
                and "BustyWomen" not in t[0]
                and "LargeButt" not in t[0]
                and "breast" not in t[0].lower()
                and "butt" not in t[0].lower()
            ]
            try:
                data_a, _ = await client.generate_image(
                    source_bytes,
                    identity_prompt,
                    negative=negative,
                    seed=seed,
                    steps=max(16, min(int(steps), 24)),
                    denoise=0.40,
                    max_width=max_side,
                    max_height=max_side,
                    flux_unet=flux_unet,
                    edit_graph="img2img",
                    denoise_cap=0.50,
                    wrap_preserve=False,
                    wrap_mode="fabric",
                    loras=identity_loras,
                    guidance=g,
                    pulid_file=pulid_file,
                    pulid_weight=0.85,
                )
                work_bytes = data_a
                extra_tags.append("pass_a_identity")
            except Exception:
                extra_tags.append("pass_a_skipped")
            from backend.ai_engine.perception.garment_mask import (
                detect_garment_mask,
                keep_outfit_edit_mask_png,
            )

            garment = None
            if perception is not None and getattr(perception, "mask", None) is not None:
                garment = perception.mask
                extra_tags.append(f"garment:{getattr(garment, 'source', 'perception')}")
            else:
                try:
                    garment = detect_garment_mask(
                        source_bytes, settings=settings, prefer_comfy=False
                    )
                    extra_tags.append(f"garment:{garment.source}")
                except Exception:
                    garment = None
                    extra_tags.append("garment_detect_failed")
            reshape_labels = {
                str(t.get("label") or "").strip().lower()
                for t in (getattr(plan, "targets", None) or [])
                if isinstance(t, dict)
            }
            scrubbed_prompt = _DO_NOT_CHANGE_SPAN.sub(" ", prompt or "")
            if reshape_labels & {"ass"} or (
                not reshape_labels
                and _ASS_HINT.search(scrubbed_prompt)
                and not _BUST_HINT.search(scrubbed_prompt)
            ):
                reshape_region = "hip"
            elif reshape_labels & {"curves"} or (
                _ASS_HINT.search(scrubbed_prompt) and _BUST_HINT.search(scrubbed_prompt)
            ):
                reshape_region = "curves"
            else:
                reshape_region = "bust"
            mask_bytes, mask_meta = keep_outfit_edit_mask_png(
                source_bytes,
                settings=settings,
                garment=garment,
                prefer_comfy=False,
                region=reshape_region,
            )
            if mask_meta.get("garment_intersect"):
                extra_tags.append("garment_intersect")
            extra_tags.append(f"{reshape_region}_inpaint")
            # Stash for soft post restore
            _garment_png = getattr(garment, "mask_png", None) if garment else None
            _edit_mask_png = mask_bytes
        else:
            _garment_png = None
            _edit_mask_png = None
            if clothed:
                from backend.ai_engine.post.face_lock import (
                    bust_inpaint_mask_png,
                    hip_inpaint_mask_png,
                )

                reshape_labels = {
                    str(t.get("label") or "").strip().lower()
                    for t in (getattr(plan, "targets", None) or [])
                    if isinstance(t, dict)
                }
                scrubbed_prompt = _DO_NOT_CHANGE_SPAN.sub(" ", prompt or "")
                if reshape_labels & {"ass"} or (
                    not reshape_labels
                    and _ASS_HINT.search(scrubbed_prompt)
                    and not _BUST_HINT.search(scrubbed_prompt)
                ):
                    mask_bytes = hip_inpaint_mask_png(work_bytes, settings=settings)
                    extra_tags.append("hip_inpaint")
                else:
                    mask_bytes = bust_inpaint_mask_png(work_bytes, settings=settings)
                    extra_tags.append("chest_inpaint")
                _edit_mask_png = mask_bytes
        gen_kwargs = dict(
            negative=negative,
            seed=seed,
            steps=steps,
            denoise=denoise,
            max_width=max_side,
            max_height=max_side,
            flux_unet=flux_unet,
            edit_graph="img2img",
            denoise_cap=denoise_cap,
            wrap_preserve=wrap_preserve,
            wrap_mode=wrap_mode,
            loras=lora_stack,
            guidance=g,
            controlnet_name=controlnet_name if use_pose_control else None,
            control_image_bytes=pose_control_bytes if use_pose_control else None,
            control_type="pose",
            control_strength=0.72 if use_pose_control else 0.65,
            control_end=0.88 if use_pose_control else 0.85,
            mask_bytes=mask_bytes,
            pulid_file=pulid_file,
            pulid_weight=0.80,
        )
        try:
            data, content_type = await client.generate_image(work_bytes, final_prompt, **gen_kwargs)
        except Exception:
            if pulid_file:
                extra_tags.append("pulid_skipped")
                gen_kwargs["pulid_file"] = None
                data, content_type = await client.generate_image(
                    work_bytes, final_prompt, **gen_kwargs
                )
            else:
                raise
        if clothed and data:
            from backend.ai_engine.post.face_lock import (
                restore_original_face,
                restore_outside_chest,
            )

            data = restore_outside_chest(
                source_bytes,
                data,
                edit_mask_png=_edit_mask_png,
                garment_mask_png=_garment_png,
            )
            data = restore_original_face(source_bytes, data)
            extra_tags.append("region_lock")
            if _edit_mask_png:
                extra_tags.append("soft_garment_restore")
    if extra_tags:
        model_label = f"{model_label}|{'|'.join(extra_tags)}"
    return data, content_type, "img", model_label


def make_runner(
    task_kind: str,
    *,
    preprocess: Optional[str] = None,
    denoise_override: Optional[float] = None,
):
    async def _runner(**kwargs: Any) -> tuple[bytes, str, str, str]:
        return await run_flux_edit(
            task_kind=task_kind,
            preprocess=preprocess,
            denoise_override=denoise_override,
            **kwargs,
        )

    return _runner

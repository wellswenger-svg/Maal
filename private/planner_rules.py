"""Rule Engine — always runs first; high-confidence simple tasks bypass VLM."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from backend.ai_engine.schema import GenerateRequest

# Below this confidence → invoke VLM (if available).
RULE_CONFIDENCE_THRESHOLD = 0.75


@dataclass
class RuleResult:
    task_type: str
    confidence: float
    bypass_vlm: bool
    warnings: list[str] = field(default_factory=list)
    targets: list[dict[str, Any]] = field(default_factory=list)
    perception: list[str] = field(default_factory=list)
    identity: dict[str, Any] = field(default_factory=dict)
    post_hints: list[str] = field(default_factory=list)
    params_hints: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


_UPSCALE = re.compile(
    r"\b(upscale|4k|8k|make\s+(it\s+)?(larger|sharper|bigger)|enhance\s+resolution|"
    r"increase\s+(the\s+)?resolution|super[\s-]?res(olution)?)\b",
    re.I,
)
_BG_REMOVE = re.compile(
    r"\b(remove\s+(the\s+)?background|cut\s*out(\s+subject)?|background\s+remov|"
    r"bg\s*remov|transparent\s+background|isolate\s+(the\s+)?subject)\b",
    re.I,
)
_I2V = re.compile(
    r"\b(animate|img2vid|image\s*to\s*video|make\s+(a\s+)?video|"
    r"turn\s+into\s+(a\s+)?video|i2v)\b",
    re.I,
)
_IMG2IMG = re.compile(r"\b(img2img|image\s*to\s*image)\b", re.I)

_CLOTHING = re.compile(
    r"\b(shirt|t-?shirt|tee|jersey|jacket|hoodie|coat|dress|skirt|pants|jeans|"
    r"trousers|shorts|suit|tie|blouse|sweater|jumper|uniform|outfit|clothes|"
    r"clothing|garment|wear(ing)?|top|bra|lingerie|bikini|swimsuit)\b",
    re.I,
)
_CLOTHING_ACTION = re.compile(
    r"\b(change|replace|swap|recolor|re-?colour|make|turn|put\s+on|wear|remove|"
    r"take\s+off|undress|strip)\b",
    re.I,
)
# Nudity / undress / NSFW body edits — must beat face/remove-object false positives
_UNDRESS = re.compile(
    r"\b(nude|naked|topless|bottomless|undress|strip(ped)?|nsfw|"
    r"no\s+clothes|without\s+clothes|fully\s+exposed|"
    r"(expose|exposing|show|showing)\s+(her|his|their|the)?\s*"
    r"(boobs?|breasts?|nipples?|chest|tits?|body)|"
    r"remove\s+(the\s+)?(top|shirt|clothes|clothing|bra|blouse|dress|jacket)|"
    r"(clothes?|clothing|top|shirt)\s+(removal|remover))\b",
    re.I,
)
# Cum / fluid overlays on face, hair, glasses, lips — image edit (not video I2V)
_FLUID = re.compile(
    r"\b(cumshot|cum\b|semen|ejaculat\w*|facial\s+(cum|splash|shot)|"
    r"splooge|spooge|jizz|spunk)\b",
    re.I,
)
_FLUID_TARGET_GLASSES = re.compile(
    r"\b(glasses|spectacles?|specs|eyeglasses|lenses?)\b", re.I
)
_FLUID_TARGET_HAIR = re.compile(r"\b(hair|hairstyle|bangs|ponytail)\b", re.I)
_FLUID_TARGET_LIPS = re.compile(r"\b(lips?|mouth|tongue)\b", re.I)
_FLUID_TARGET_FACE = re.compile(
    r"\b(face|facial|cheeks?|forehead|chin|nose)\b", re.I
)
# Body-wide fluid + undress (not "do not undress" clothed facial cumshots)
_FLUID_WITH_UNDRESS = re.compile(
    r"\b("
    r"fully\s+nude|remove\s+all\s+clothing|nude\s+body|naked\s+body|"
    r"bare\s+skin|cover\s+her\s+nude|drenched\s+across|"
    r"soaking\s+her\s+bare|her\s+nude\s+body"
    r")\b",
    re.I,
)
_KEEP_CLOTHES = re.compile(
    r"\b("
    r"do\s+not\s+undress|don'?t\s+undress|keep\s+(her\s+)?(clothes|clothing)|"
    r"keep\s+clothes|do\s+not\s+make\s+her\s+(nude|topless)"
    r")\b",
    re.I,
)


def _fluid_wants_undress(text: str) -> bool:
    """True when fluid edit should also strip clothes (body drench)."""
    if _KEEP_CLOTHES.search(text):
        return False
    return bool(_FLUID_WITH_UNDRESS.search(text) or (
        _EXPLICIT_UNDRESS.search(text)
        and re.search(r"\b(breasts?|stomach|thighs?|body|neck)\b", text, re.I)
        and re.search(r"\b(drench|drenched|soak|soaking|cover|covered)\b", text, re.I)
    ))


def _fluid_target_label(text: str) -> str:
    # Explicit primary targets beat broad "face" mentions in identity-lock boilerplate
    lips_primary = bool(
        re.search(
            r"\b(on|onto|across)\s+(her\s+)?(lips?|mouth)\b|"
            r"\b(lips?|mouth)\s+only\b|"
            r"\bcum\s+on\s+(her\s+)?(lips?|mouth)\b",
            text,
            re.I,
        )
    )
    glasses_primary = bool(
        re.search(
            r"\b(on|onto|across)\s+(her\s+)?(glasses|lenses|specs|spectacles?)\b|"
            r"\b(glasses|lenses)\s+only\b|"
            r"\bcum\s+on\s+(her\s+)?(glasses|lenses|specs)\b",
            text,
            re.I,
        )
    )
    # Positive full-face coverage (not "without covering cheeks…")
    full_face_cover = bool(
        re.search(
            r"\b("
            r"facial\s+cumshot|entire\s+face|full\s+(facial|face)|"
            r"(on|across)\s+(her\s+)?(face|cheeks?|forehead)"
            r")\b",
            text,
            re.I,
        )
    )
    if lips_primary and not full_face_cover:
        return "lips"
    if glasses_primary and not full_face_cover:
        return "glasses"

    # Facial cumshot wins over incidental "glasses" mentions in the same prompt
    if _FLUID_TARGET_FACE.search(text) and not (
        _FLUID_TARGET_GLASSES.search(text)
        and not re.search(r"\b(face|facial|cheeks?|forehead)\b", text, re.I)
    ):
        if re.search(r"\b(face|facial|cheeks?|forehead)\b", text, re.I):
            return "face"
    if _FLUID_TARGET_GLASSES.search(text):
        return "glasses"
    if _FLUID_TARGET_LIPS.search(text) and not _FLUID_TARGET_FACE.search(text):
        return "lips"
    if _FLUID_TARGET_HAIR.search(text) and not _FLUID_TARGET_FACE.search(text):
        return "hair"
    if _FLUID_TARGET_FACE.search(text):
        return "face"
    if _FLUID_TARGET_HAIR.search(text):
        return "hair"
    if _FLUID_TARGET_LIPS.search(text):
        return "lips"
    return "face"


# Img act edits (Flux LoRAs) — before undress / pose so BJ/HJ/titjob win.
_ACT_ORAL = re.compile(
    r"\b(blowjob|bj\b|oral|fellatio|deepthroat|giving\s+head|"
    r"suck(s|ing)?\s+(his|a|the|an)?\s*(erect\s+)?(penis|dick|cock)|"
    r"sucks?\s+his\s+erect\s+penis)\b",
    re.I,
)
_ACT_HANDJOB = re.compile(
    r"\b(handjob|hand[\s-]?job|hj\b|stroking\s+(his|a|the)?\s*(erect\s+)?"
    r"(penis|dick|cock)|hand\s+on\s+(his|a|the)\s+(erect\s+)?(penis|dick|cock))\b",
    re.I,
)
_ACT_TITJOB = re.compile(
    r"\b(titjob|tit[\s-]?job|tittyfuck|paizuri|boobjob|boob[\s-]?job|"
    r"penis\s+between\s+(her\s+)?breasts|between\s+(her\s+)?breasts)\b",
    re.I,
)

# Rear / all-fours pose change (image edit — not video doggy sex)
_POSE_REAR = re.compile(
    r"\b("
    r"all\s+fours|on\s+all\s+fours|hands?\s+and\s+knees|"
    r"bent\s+over|bend(ing)?\s+over|ass\s+up|"
    r"rear\s+view|from\s+behind\s+pose|doggy\s*style\s*pose|"
    r"on\s+her\s+hands\s+and\s+knees"
    r")\b",
    re.I,
)


def _pose_wants_undress(text: str) -> bool:
    if _KEEP_CLOTHES.search(text):
        return False
    return bool(
        _EXPLICIT_UNDRESS.search(text)
        or re.search(r"\b(fully\s+nude|nude\s+pose|naked\s+pose|remove\s+all\s+clothing)\b", text, re.I)
    )


# Clothed body-size enhance (cleavage / ass) — must NOT route to undress
_BODY_CURVE = re.compile(
    r"\b(breasts?|boobs?|tits?|cleavage|bust|chest|"
    r"ass|butts?|booty|hips|glutes?|thighs?|curves?)\b",
    re.I,
)
_SIZE_ENHANCE = re.compile(
    r"\b(bigger|larger|fuller|rounder|huge|enhance[d]?|enlarg(e|ed|ing)|"
    r"increase[d]?|boost(ed)?|volum(e|inous)|push[\s-]?up|size\s*up|"
    r"more\s+(voluminous|prominent|pronounced|cleavage)|"
    r"make\b.{0,28}\b(bigger|larger|fuller|rounder|enhance))\b",
    re.I,
)
_EXPLICIT_UNDRESS = re.compile(
    r"\b(nude|naked|topless|bottomless|undress|strip(ped)?|"
    r"no\s+clothes|without\s+clothes|remove\s+(the\s+)?"
    r"(clothes|clothing|top|shirt|bra|dress)|"
    r"(expose|exposing|show|showing)\s+(her|his|their|the)?\s*"
    r"(nipples?|breasts?|boobs?|tits?|chest))\b",
    re.I,
)
# Wet / see-through shirt — clothes stay on, fabric goes sheer (not full nude)
_WET_SHEER = re.compile(
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
# "no sheer fabric" in clothed presets must not classify as wet/see-through.
_NEGATED_SHEER = re.compile(
    r"\b(?:no|not|without|don'?t)\s+(?:see[\s-]?through|sheer|transparent)(?:\s+\w+)?",
    re.I,
)


def _body_enhance_label(text: str) -> str:
    # Ignore "do not change her ass/breasts" lock phrases when picking the target
    scrubbed = re.sub(
        r"\b(do\s+not|don'?t)\s+change\s+(her\s+)?[^.]{0,40}",
        " ",
        text,
        flags=re.I,
    )
    has_bust = bool(
        re.search(r"\b(breasts?|boobs?|tits?|cleavage|bust|chest)\b", scrubbed, re.I)
    )
    has_ass = bool(
        re.search(r"\b(ass|butts?|booty|hips|glutes?|thighs?)\b", scrubbed, re.I)
    )
    if has_bust and has_ass:
        return "curves"
    if has_ass:
        return "ass"
    if re.search(r"\b(cleavage|bust)\b", scrubbed, re.I):
        return "cleavage"
    if has_bust:
        return "breasts"
    return "curves"
# "keep the face" / "don't change face" is identity lock, not a face edit
_FACE_LOCK_ONLY = re.compile(
    r"\b(keep|preserve|same|don'?t\s+change|do\s+not\s+change|intact)\b.{0,40}\b"
    r"(face|facial|identity|hair|pose|background)\b|"
    r"\b(face|facial|identity)\b.{0,40}\b"
    r"(keep|preserve|unchanged|intact|same|don'?t\s+change)\b",
    re.I,
)
_FACE = re.compile(
    r"\b(face|facial|smile|smiling|eyes?|lips?|expression|makeup|make-?up|"
    r"beard|mustache|age(d|ing)?|wrinkle)\b",
    re.I,
)
_HAIR = re.compile(
    r"\b(hair|hairstyle|haircut|blonde|brunette|bald|ponytail|bangs)\b",
    re.I,
)
_BG_REPLACE = re.compile(
    r"\b(change|replace|swap)\s+(the\s+)?background\b|"
    r"\b(new|different)\s+background\b|"
    r"\bput\s+(him|her|them|me|subject)\s+(on|in|at)\b",
    re.I,
)
_REMOVE_OBJ = re.compile(
    r"\b(remove|delete|erase|get\s+rid\s+of)\s+(the\s+)?"
    r"(people|person|man|woman|car|object|logo|text|watermark|bag|phone|hat|glasses)\b|"
    r"\b(delete|erase)\s+(the\s+)?\w+\b",
    re.I,
)
_ADD_OBJ = re.compile(
    r"\b(add|insert|place|put)\s+(a|an|the)\s+\w+",
    re.I,
)
_STYLE = re.compile(
    r"\b(pixar|anime|cartoon|oil\s+paint|watercolor|sketch|cyberpunk|"
    r"style\s+transfer|in\s+the\s+style\s+of|make\s+it\s+look\s+like)\b",
    re.I,
)
_FACE_SWAP = re.compile(r"\b(face\s*swap|swap\s+(the\s+)?faces?)\b", re.I)
_OUTPAINT = re.compile(
    r"\b(outpaint|extend\s+(the\s+)?(canvas|image|frame)|expand\s+(the\s+)?(image|borders?))\b",
    re.I,
)
_INPAINT = re.compile(r"\b(inpaint|fill\s+in\s+(the\s+)?(hole|mask|area))\b", re.I)
_RESTORE = re.compile(
    r"\b(restor(e|ation)|denois(e|ing)|fix\s+(old|damaged|scratch)|colorize)\b",
    re.I,
)
_PRODUCT = re.compile(
    r"\b(product\s+(shot|photo|photography)|studio\s+(light|background|shot)|"
    r"ecommerce|catalogue|catalog\s+image)\b",
    re.I,
)
_AMBIGUOUS = re.compile(
    r"^\s*(fix(\s+it)?|improve(\s+it)?|enhance(\s+it)?|make\s+it\s+better|"
    r"edit(\s+this)?|do\s+something|help|update(\s+it)?)\s*\.?\s*$",
    re.I,
)
_MULTI_STEP = re.compile(r"\b(and\s+then|then\s+|also\s+|after\s+that|, then)\b", re.I)


def classify(req: "GenerateRequest") -> RuleResult:
    """
    Classify task_type with confidence.

    High-confidence simple classes set bypass_vlm=True (no VLM load).
    Ambiguous / multi-step / low confidence → bypass_vlm=False.
    """
    text = f"{req.prompt} {req.prompt_english}".strip()
    user = (req.prompt or "").strip()

    # --- VLM bypass band (architecture: upscale, bg remove, img2img, img2vid) ---
    if req.mode == "vid" or _I2V.search(text):
        from backend.ai_engine.workflows.video_i2v.motion import extract_motion_hints

        motion = extract_motion_hints(text)
        return RuleResult(
            task_type="video.i2v",
            confidence=0.96,
            bypass_vlm=True,
            reason="i2v_mode_or_keyword",
            perception=[],
            post_hints=[],
            params_hints={"motion": motion},
        )

    if _UPSCALE.search(text) and not _CLOTHING.search(text) and not _FACE.search(text):
        return RuleResult(
            task_type="image.upscale",
            confidence=0.94,
            bypass_vlm=True,
            reason="upscale_keyword",
            post_hints=["upscale"],
        )

    if _BG_REMOVE.search(text) and not _BG_REPLACE.search(text):
        return RuleResult(
            task_type="image.background_remove",
            confidence=0.93,
            bypass_vlm=True,
            reason="background_remove_keyword",
            perception=["matting"],
        )

    if _IMG2IMG.search(text) and len(user.split()) <= 6:
        return RuleResult(
            task_type="image.img2img",
            confidence=0.90,
            bypass_vlm=True,
            reason="explicit_img2img",
        )

    # --- Clear specialized edits (high confidence → still bypass VLM) ---
    if _FACE_SWAP.search(text):
        return RuleResult(
            task_type="edit.face_swap",
            confidence=0.92,
            bypass_vlm=True,
            reason="face_swap_keyword",
            identity={"enabled": True, "method": "reactor"},
            perception=["face_detect"],
        )

    # Img act edits (BJ / HJ / titjob) before fluid/undress — Flux act LoRAs.
    if req.mode != "vid":
        if _ACT_ORAL.search(text) and not _ACT_TITJOB.search(text):
            return RuleResult(
                task_type="edit.general_instruction",
                confidence=0.94,
                bypass_vlm=True,
                reason="img_act_oral_pov_pattern",
                targets=[{"label": "body", "role": "act_region"}],
                perception=[],
                identity={"enabled": True, "method": "pulid"},
                post_hints=["face_detailer"],
                params_hints={
                    "loras": [
                        "clothes_remover",
                        "nsfw_unlock",
                        "oral_pov",
                        "male_anatomy",
                    ],
                    "nsfw_edit": True,
                    "act_edit": "oral",
                    "denoise": 0.95,
                },
            )
        if _ACT_HANDJOB.search(text) and not _ACT_ORAL.search(text):
            return RuleResult(
                task_type="edit.general_instruction",
                confidence=0.94,
                bypass_vlm=True,
                reason="img_act_handjob_pattern",
                targets=[{"label": "body", "role": "act_region"}],
                perception=[],
                identity={"enabled": True, "method": "pulid"},
                post_hints=["face_detailer"],
                params_hints={
                    "loras": [
                        "clothes_remover",
                        "nsfw_unlock",
                        "male_anatomy",
                        "detailed_hands",
                    ],
                    "nsfw_edit": True,
                    "act_edit": "handjob",
                    "denoise": 0.94,
                },
            )
        if _ACT_TITJOB.search(text):
            return RuleResult(
                task_type="edit.general_instruction",
                confidence=0.94,
                bypass_vlm=True,
                reason="img_act_titjob_pattern",
                targets=[{"label": "body", "role": "act_region"}],
                perception=[],
                identity={"enabled": True, "method": "pulid"},
                post_hints=["face_detailer"],
                params_hints={
                    "loras": [
                        "clothes_remover",
                        "nsfw_unlock",
                        "breast_enhance",
                        "male_anatomy",
                    ],
                    "nsfw_edit": True,
                    "act_edit": "titjob",
                    "denoise": 0.94,
                },
            )

    # Cum / fluid overlays before face/hair/undress (avoids expression-only + undress traps).
    # Use general_instruction (Kontext-first) — add_object prefers Flux Fill and rewrites faces.
    if _FLUID.search(text) and req.mode != "vid":
        if _fluid_wants_undress(text):
            return RuleResult(
                task_type="edit.general_instruction",
                confidence=0.94,
                bypass_vlm=True,
                reason="fluid_undress_overlay_pattern",
                targets=[{"label": "body", "role": "add_region"}],
                perception=[],
                identity={"enabled": True, "method": "pulid"},
                post_hints=["face_detailer", "fluid_recolor"],
                params_hints={
                    "loras": ["clothes_remover", "nsfw_unlock", "cof"],
                    "nsfw_edit": True,
                    "fluid_edit": True,
                    "undress_fluid": True,
                    "denoise": 0.92,
                },
            )
        label = _fluid_target_label(text)
        # Milder denoise when the Dev img2img fallback is used; Kontext ignores denoise.
        # Face/lips stay lower so the model overlays translucent fluid instead of
        # painting a solid white mask over the face.
        denoise = 0.60 if label in ("face", "lips") else 0.68
        return RuleResult(
            task_type="edit.general_instruction",
            confidence=0.93,
            bypass_vlm=True,
            reason="fluid_overlay_pattern",
            targets=[{"label": label, "role": "add_region"}],
            perception=[],  # full-frame Kontext; region masks often miss thin fluids
            identity={"enabled": True, "method": "pulid"},
            post_hints=["face_detailer", "fluid_recolor"],
            params_hints={
                "loras": ["nsfw_unlock", "cof"],
                "nsfw_edit": True,
                "fluid_edit": True,
                "denoise": denoise,
            },
        )

    # Clothed cleavage/ass size-up BEFORE undress — "bigger boobs" must not strip clothes
    if (
        req.mode != "vid"
        and _BODY_CURVE.search(text)
        and _SIZE_ENHANCE.search(text)
        and not _POSE_REAR.search(text)
        # Allow "do not make her nude" boilerplate; block only real undress intent
        and not (
            _EXPLICIT_UNDRESS.search(text) and not _KEEP_CLOTHES.search(text)
        )
    ):
        label = _body_enhance_label(text)
        denoise = 0.62 if label in ("ass", "breasts", "cleavage") else 0.60
        loras = ["nsfw_unlock"]
        if label in ("cleavage", "breasts", "curves"):
            loras.append("breast_enhance")
        if label in ("ass", "curves"):
            loras.append("ass_enhance")
        return RuleResult(
            task_type="edit.keep_outfit_reshape",
            confidence=0.92,
            bypass_vlm=True,
            reason="clothed_body_enhance_pattern",
            targets=[{"label": label, "role": "reshape_region"}],
            perception=["garment"],
            identity={"enabled": True, "method": "pulid"},
            post_hints=["face_detailer", "color_match"],
            params_hints={
                "loras": loras,
                "nsfw_edit": True,
                "clothed_enhance": True,
                "denoise": denoise,
                "garment_mask": True,
            },
        )

    # Rear pose change BEFORE plain undress so "nude all fours" keeps pose intent
    if _POSE_REAR.search(text) and req.mode != "vid":
        wants_nude = _pose_wants_undress(text)
        if wants_nude:
            return RuleResult(
                task_type="edit.general_instruction",
                confidence=0.93,
                bypass_vlm=True,
                reason="pose_rear_undress_pattern",
                targets=[{"label": "body", "role": "pose_region"}],
                perception=[],  # face_view is scanned in edit_runner from the start image
                identity={"enabled": True, "method": "pulid"},
                post_hints=["face_detailer"],
                params_hints={
                    "loras": ["clothes_remover", "nsfw_unlock"],
                    "nsfw_edit": True,
                    "pose_edit": True,
                    "pose_undress": True,
                    "denoise": 0.88,
                },
            )
        return RuleResult(
            task_type="edit.general_instruction",
            confidence=0.92,
            bypass_vlm=True,
            reason="pose_rear_clothed_pattern",
            targets=[{"label": "body", "role": "pose_region"}],
            perception=[],
            identity={"enabled": True, "method": "pulid"},
            post_hints=["face_detailer", "color_match"],
            params_hints={
                "loras": ["nsfw_unlock"],
                "nsfw_edit": True,
                "pose_edit": True,
                "pose_undress": False,
                "denoise": 0.86,
            },
        )

    # Wet / see-through shirt BEFORE undress — keep garment on, make fabric sheer
    sheer_text = _NEGATED_SHEER.sub(" ", text)
    if _WET_SHEER.search(sheer_text) and req.mode != "vid" and not _POSE_REAR.search(text):
        # Explicit full undress still wins if they also asked to remove clothes
        if not (
            re.search(r"\b(fully\s+nude|remove\s+all\s+clothing|no\s+clothes)\b", text, re.I)
            and not _KEEP_CLOTHES.search(text)
        ):
            return RuleResult(
                task_type="edit.general_instruction",
                confidence=0.93,
                bypass_vlm=True,
                reason="wet_sheer_shirt_pattern",
                targets=[{"label": "shirt", "role": "fabric_region"}],
                perception=[],
                identity={"enabled": True, "method": "pulid"},
                post_hints=["face_detailer"],
                params_hints={
                    "loras": ["nsfw_unlock", "see_through", "wet_shirt"],
                    "nsfw_edit": True,
                    "wet_sheer": True,
                    "denoise": 0.92,
                },
            )

    # Undress / NSFW body edits before face/remove (avoids "keep the face" trap)
    if _UNDRESS.search(text):
        return RuleResult(
            task_type="edit.clothing_replace",
            confidence=0.93,
            bypass_vlm=True,
            reason="undress_nsfw_pattern",
            targets=[{"label": "clothing", "role": "replace_region"}],
            perception=[],  # full-frame Kontext; heuristic masks hurt undress
            identity={"enabled": False},
            post_hints=[],
            params_hints={
                "loras": ["clothes_remover", "nsfw_unlock"],
                "nsfw_edit": True,
                "denoise": 1.0,
            },
        )

    if _CLOTHING.search(text) and _CLOTHING_ACTION.search(text):
        label = _first_group(
            text,
            r"\b(shirt|t-?shirt|jersey|jacket|hoodie|dress|pants|jeans|coat|skirt|suit|top|bra)\b",
        ) or "clothing"
        return RuleResult(
            task_type="edit.clothing_replace",
            confidence=0.91,
            bypass_vlm=True,
            reason="clothing_replace_pattern",
            targets=[{"label": label, "role": "replace_region"}],
            perception=["grounding", "sam2"],
            identity={"enabled": True, "method": "pulid"},
            post_hints=["face_detailer", "color_match"],
        )

    if _HAIR.search(text) and _CLOTHING_ACTION.search(text):
        return RuleResult(
            task_type="edit.hair",
            confidence=0.88,
            bypass_vlm=True,
            reason="hair_edit_pattern",
            targets=[{"label": "hair", "role": "replace_region"}],
            perception=["grounding", "sam2"],
            identity={"enabled": True, "method": "pulid"},
            post_hints=["face_detailer"],
        )

    # Ignore "keep/preserve the face" identity locks when classifying face edits
    face_hit = _FACE.search(text)
    if (
        face_hit
        and _CLOTHING_ACTION.search(text)
        and not _CLOTHING.search(text)
        and not _FACE_LOCK_ONLY.search(text)
    ):
        return RuleResult(
            task_type="edit.face",
            confidence=0.88,
            bypass_vlm=True,
            reason="face_edit_pattern",
            targets=[{"label": "face", "role": "replace_region"}],
            perception=["face_detect"],
            identity={"enabled": True, "method": "pulid"},
            post_hints=["face_detailer"],
        )

    if _BG_REPLACE.search(text):
        return RuleResult(
            task_type="edit.background",
            confidence=0.90,
            bypass_vlm=True,
            reason="background_replace_pattern",
            perception=["matting"],
            post_hints=["color_match"],
        )

    if _REMOVE_OBJ.search(text) and not _CLOTHING.search(text) and not _UNDRESS.search(text):
        return RuleResult(
            task_type="edit.remove_object",
            confidence=0.86,
            bypass_vlm=True,
            reason="remove_object_pattern",
            perception=["grounding", "sam2"],
            post_hints=["color_match"],
        )

    if _OUTPAINT.search(text):
        return RuleResult(
            task_type="edit.outpaint",
            confidence=0.90,
            bypass_vlm=True,
            reason="outpaint_keyword",
        )

    if _INPAINT.search(text):
        return RuleResult(
            task_type="edit.inpaint",
            confidence=0.88,
            bypass_vlm=True,
            reason="inpaint_keyword",
            perception=["sam2"],
        )

    if _STYLE.search(text):
        return RuleResult(
            task_type="edit.style_transfer",
            confidence=0.87,
            bypass_vlm=True,
            reason="style_keyword",
        )

    if _RESTORE.search(text):
        return RuleResult(
            task_type="edit.restore",
            confidence=0.86,
            bypass_vlm=True,
            reason="restore_keyword",
            post_hints=["face_detailer"],
        )

    if _PRODUCT.search(text):
        return RuleResult(
            task_type="edit.product",
            confidence=0.85,
            bypass_vlm=True,
            reason="product_keyword",
            perception=["matting"],
        )

    if _ADD_OBJ.search(text) and not _CLOTHING.search(text):
        return RuleResult(
            task_type="edit.add_object",
            confidence=0.80,
            bypass_vlm=True,
            reason="add_object_pattern",
            perception=["grounding", "sam2"],
        )

    # --- Needs VLM ---
    if _AMBIGUOUS.search(user) or _MULTI_STEP.search(text):
        return RuleResult(
            task_type="edit.general_instruction",
            confidence=0.45,
            bypass_vlm=False,
            reason="ambiguous_or_multistep",
            warnings=["needs_vlm"],
        )

    if len(user.split()) <= 2 and req.mode == "img":
        return RuleResult(
            task_type="edit.general_instruction",
            confidence=0.50,
            bypass_vlm=False,
            reason="too_short",
            warnings=["needs_vlm"],
        )

    # Generic image edit — medium confidence; VLM optional enrichment
    if req.mode == "img":
        conf = 0.72 if len(user.split()) < 5 else 0.78
        return RuleResult(
            task_type="edit.general_instruction",
            confidence=conf,
            bypass_vlm=conf >= RULE_CONFIDENCE_THRESHOLD,
            reason="general_instruction",
            identity={"enabled": True, "method": "pulid"},
        )

    return RuleResult(
        task_type="image.img2img",
        confidence=0.65,
        bypass_vlm=False,
        reason="fallback",
        warnings=["needs_vlm"],
    )


def classify_task_type(req: "GenerateRequest") -> tuple[str, float, list[str]]:
    """Backward-compatible tuple API used by older tests."""
    r = classify(req)
    return r.task_type, r.confidence, list(r.warnings)


def _first_group(text: str, pattern: str) -> Optional[str]:
    m = re.search(pattern, text, flags=re.I)
    if not m:
        return None
    return m.group(1).lower()

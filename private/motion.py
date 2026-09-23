"""Motion hint extraction + Wan I2V prompt scaffolding (no workflow names)."""

from __future__ import annotations

import re
from typing import Any


_PAN = re.compile(r"\b(pan|dolly|truck|slide|orbit)\b", re.I)
_ZOOM = re.compile(r"\b(zoom|push[\s-]?in|pull[\s-]?out|dolly\s+in|dolly\s+out)\b", re.I)
_STATIC = re.compile(r"\b(static|still|subtle|gentle|slight|minimal\s+motion)\b", re.I)
_FAST = re.compile(r"\b(fast|rapid|dynamic|energetic|intense)\b", re.I)
_SMILE = re.compile(r"\b(smile|smiling|grin)\b", re.I)
_WALK = re.compile(r"\b(walk|walking|run|running|turn|turning|nod|wave)\b", re.I)
_CAMERA = re.compile(r"\b(camera|cinematic|tracking\s+shot)\b", re.I)

# Named NSFW poses — wired to LoRA allowlists in lora_stack._action_allows.
_NSFW_ACT = re.compile(
    r"\b(sex|fuck|fucking|blowjob|bj|deepthroat|oral|penis|dick|cock|pussy|"
    r"vagina|cum|cumshot|facial|missionary|cowgirl|riding|doggy|doggystyle|"
    r"thrust|penetrat|naked|nude|strip|handjob|hj|stroke|stroking|"
    r"genital|topless|bottomless|suck|sucking)\b",
    re.I,
)
_ORAL = re.compile(
    r"\b(blowjob|bj|deepthroat|oral|suck|sucks|sucking|mouth|lips)\b",
    re.I,
)
_DEEPTHROAT = re.compile(r"\bdeepthroat\b", re.I)
_PENETRATION = re.compile(
    r"\b(sex|fuck|fucking|missionary|cowgirl|riding|doggy|doggystyle|"
    r"doggy[\s-]?style|from\s+behind|thrust|penetrat|pussy|vagina)\b",
    re.I,
)
_MISSIONARY = re.compile(r"\bmissionary\b", re.I)
_COWGIRL = re.compile(r"\b(cowgirl|riding|reverse\s*cowgirl)\b", re.I)
_DOGGY = re.compile(
    r"\b(doggy|doggystyle|doggy[\s-]?style|from\s+behind)\b",
    re.I,
)
_HANDJOB = re.compile(
    r"\b(handjob|hand[\s-]?job|hj|stroke|stroking)\b",
    re.I,
)
_CUMSHOT = re.compile(
    r"\b(cumshot|cum[\s-]?shot|facial|ejaculat|cum)\b",
    re.I,
)
_ORAL_INSERTION = re.compile(
    r"\b(oral\s*insertion|insert(ing|ion)?\s+(into\s+)?(her\s+)?(mouth|lips)|"
    r"tip\s+into\s+(her\s+)?mouth|mouth\s+insertion)\b",
    re.I,
)
_REVEAL_PENIS = re.compile(
    r"\b(reveal\s+(his\s+)?penis|penis\s+reveal|show\s+(his\s+)?(erect\s+)?penis|"
    r"pull\s+out\s+(his\s+)?penis|unzip|flash\s+(his\s+)?penis)\b",
    re.I,
)
_JIGGLE = re.compile(
    r"\b(jiggle|jiggling|jingle|jingling|bounce|bouncing|wobble|wobbling|"
    r"boob\s*bounce|breast\s*bounce|breast\s*jiggle|titty\s*bounce|"
    r"shake\s+(her\s+)?(boobs?|breasts?|tits?)|"
    r"(boobs?|breasts?|tits?)\s+(shake|shaking|jiggle|jiggling|bounce|bouncing))\b",
    re.I,
)
_TWERK = re.compile(
    r"\b(twerk|twerking|twerked|"
    r"ass\s*(shake|shaking|jiggle|jiggling|bounce|bouncing)|"
    r"booty\s*(shake|shaking|jiggle|jiggling|bounce|bouncing)|"
    r"butt\s*(shake|shaking|jiggle|jiggling|bounce|bouncing))\b",
    re.I,
)

# Pose id → short motion cue (kept tiny — long scaffolds dilute Wan face lock).
POSE_SCAFFOLDS: dict[str, str] = {
    "oral": (
        "complete blowjob and deepthroat on one man with one attached erect penis, "
        "continuous in-and-out head bobbing for the whole clip"
    ),
    "deepthroat": (
        "deepthroat on one man with one attached erect penis, "
        "repeated deep oral strokes for the whole clip"
    ),
    "oral_insertion": "oral insertion — erect penis tip entering her mouth",
    "reveal_penis": "reveal erect penis in frame",
    "jiggle": (
        "her breasts bounce, shake, jiggle and sway continuously — "
        "clear soft-tissue bounce under the clothes, not frozen"
    ),
    "twerk": (
        "twerking and ass shaking — twerks causing her ass to jiggle and shake "
        "continuously, clear booty bounce, not frozen"
    ),
    "missionary": "missionary thrusting with erect penis in vagina",
    "cowgirl": "cowgirl riding with erect penis in vagina",
    "doggy": "doggy thrusting with erect penis entering from behind",
    "handjob": "hand stroking his erect penis",
    "cumshot": "visible cumshot with man in frame",
    "penetration": "continuous penetrative thrusting",
}

# Kept for tests / callers; NSFW scaffold no longer dumps these (CLIP dilution).
POSE_SEQUENCES: dict[str, str] = {
    "oral": (
        "in the same scene a man with one connected erect penis is with her, "
        "she takes him into her mouth, then full continuous blowjob for the whole clip. "
    ),
    "deepthroat": (
        "in the same scene a man with one connected erect penis is with her, "
        "deepthroat begins, then repeated deep oral strokes for the whole clip. "
    ),
    "oral_insertion": "erect tip approaches lips, then enters mouth. ",
    "reveal_penis": "man is with her, then erect penis is revealed. ",
    "jiggle": (
        "she starts moving so her breasts bounce, then continuous jiggle and sway "
        "for the whole clip. "
    ),
    "twerk": (
        "she starts twerking, then continuous ass shaking and booty jiggle "
        "for the whole clip. "
    ),
    "missionary": "missionary position, then penetration, then continuous thrusting. ",
    "cowgirl": "cowgirl mount, then penetration, then continuous riding. ",
    "doggy": "doggy position, then penetration, then continuous thrusting. ",
    "handjob": "man is with her, then hand grips shaft, then continuous stroking. ",
    "cumshot": "build to climax, then visible cumshot. ",
    "penetration": "penetration begins, then continuous thrusting. ",
}

# Preferred sequence when multiple pose kinds match (most specific first).
_SEQUENCE_PRIORITY = (
    "deepthroat",
    "oral_insertion",
    "reveal_penis",
    "twerk",
    "jiggle",
    "missionary",
    "cowgirl",
    "doggy",
    "handjob",
    "cumshot",
    "oral",
    "penetration",
)


def extract_motion_hints(text: str) -> dict[str, Any]:
    """Derive motion params from user language for I2V scaffolds."""
    t = text or ""
    nsfw = bool(_NSFW_ACT.search(t))
    amplitude = "medium"
    if _STATIC.search(t) and not nsfw:
        amplitude = "low"
    elif _FAST.search(t) or nsfw:
        amplitude = "high"

    kinds: list[str] = []
    if nsfw:
        kinds.append("nsfw_action")
        if _ORAL.search(t):
            kinds.append("oral")
        if _DEEPTHROAT.search(t):
            kinds.append("deepthroat")
        if _PENETRATION.search(t):
            kinds.append("penetration")
        if _MISSIONARY.search(t):
            kinds.append("missionary")
        if _COWGIRL.search(t):
            kinds.append("cowgirl")
        if _DOGGY.search(t):
            kinds.append("doggy")
        if _HANDJOB.search(t):
            kinds.append("handjob")
        if _CUMSHOT.search(t):
            kinds.append("cumshot")
        if _ORAL_INSERTION.search(t):
            kinds.append("oral_insertion")
            if "oral" not in kinds:
                kinds.append("oral")
        if _REVEAL_PENIS.search(t):
            kinds.append("reveal_penis")
        # Freeform "sex"/"fuck" without a named pose → missionary LoRA (Sex button parity).
        if "penetration" in kinds and not any(
            k in kinds
            for k in (
                "missionary",
                "cowgirl",
                "doggy",
                "oral",
                "deepthroat",
                "handjob",
                "oral_insertion",
                "reveal_penis",
            )
        ):
            kinds.append("missionary")
        # Oral: keep motion readable (not frozen tip-lick) but not jumpcut-fast.
        if "oral" in kinds or "deepthroat" in kinds:
            amplitude = "medium"
    # Clothed / freeform breast bounce — works without NSFW keywords.
    if _JIGGLE.search(t):
        kinds.append("jiggle")
        amplitude = "high"
    # Ass shake / twerk — prefer over bare "bounce" breast jiggle when both match.
    if _TWERK.search(t):
        kinds.append("twerk")
        amplitude = "high"
        if "jiggle" in kinds and not re.search(
            r"\b(boobs?|breasts?|tits?|cleavage)\b", t, re.I
        ):
            kinds = [k for k in kinds if k != "jiggle"]
    if _PAN.search(t):
        kinds.append("pan")
    if _ZOOM.search(t):
        kinds.append("zoom")
    if _SMILE.search(t):
        kinds.append("expression")
    if _WALK.search(t):
        kinds.append("body")
    if _CAMERA.search(t) and "pan" not in kinds:
        kinds.append("camera")
    if not kinds:
        kinds = ["subtle_life"]

    return {
        "motion_kinds": kinds,
        "amplitude": amplitude,
        "preserve_identity": True,
        "lock_start_frame": True,
        "nsfw": nsfw,
    }


def _pick_sequence(kinds: list[str]) -> str:
    """Return a short sequence cue for the highest-priority matched pose."""
    kind_set = {str(k) for k in kinds}
    for key in _SEQUENCE_PRIORITY:
        if key in kind_set:
            return POSE_SEQUENCES.get(key, "")
    return ""


def scaffold_i2v_prompt(
    user_prompt: str,
    motion: dict[str, Any] | None = None,
    *,
    raw_prompt: bool = True,
) -> str:
    """
    Build Wan I2V positive prompt. Raw mode leads with the user text.

    NSFW prompts stay short on purpose: long identity/anatomy/sequence dumps
    dilute UMT5 attention and mush the start-frame face.
    """
    motion = motion or {}
    amp = motion.get("amplitude") or "medium"
    kinds = motion.get("motion_kinds") or ["subtle_life"]
    nsfw = bool(motion.get("nsfw")) or bool(_NSFW_ACT.search(user_prompt or ""))
    amp_phrase = {
        "low": "very subtle, minimal movement",
        "medium": "natural moderate motion",
        "high": "clear dynamic motion",
    }.get(str(amp), "natural moderate motion")
    if nsfw and ("oral" in {str(k) for k in kinds} or "deepthroat" in {str(k) for k in kinds}):
        amp_phrase = "clear rhythmic full strokes, visible shaft travel"

    kind_bits = []
    for k in kinds:
        if nsfw and str(k) in ("nsfw_action", "subtle_life"):
            # Skip generic NSFW filler — user text + one pose cue is enough.
            continue
        phrase = {
            "pan": "slow horizontal camera pan",
            "zoom": "gentle camera zoom",
            "expression": "natural facial expression change",
            "body": "natural body motion",
            "camera": "cinematic camera move",
            "nsfw_action": "explicit continuous sexual action",
            "subtle_life": "subtle natural motion (breathing, micro-expression)",
            **POSE_SCAFFOLDS,
        }.get(str(k), str(k))
        kind_bits.append(phrase)
    # One primary pose cue only for NSFW (avoid oral+penetration+cumshot pile-up).
    if nsfw and kind_bits:
        primary = ""
        for key in _SEQUENCE_PRIORITY:
            if key in {str(k) for k in kinds} and key in POSE_SCAFFOLDS:
                primary = POSE_SCAFFOLDS[key]
                break
        motion_line = primary or kind_bits[0]
        seq = _pick_sequence([str(k) for k in kinds])
        oralish_kinds = "oral" in {str(k) for k in kinds} or "deepthroat" in {
            str(k) for k in kinds
        }
        # Oral scaffold already states the full sequence — don't double-prefix.
        if seq and not oralish_kinds:
            motion_line = f"{seq.strip().rstrip('.')} — {motion_line}"
    else:
        motion_line = "; ".join(kind_bits) if kind_bits else "subtle natural motion"

    edit = (user_prompt or "").strip() or "gentle natural motion"
    if nsfw and "PENISLORA" not in edit.upper():
        # Trigger token for PENISLORA_22 when that LoRA is loaded.
        edit = f"{edit}. PENISLORA"
    kinds_l = [str(k) for k in kinds]
    # Jiggle / jingle: Oral-quality whole-scene prompt so I2V gets a clear bounce driver.
    if "jiggle" in kinds_l and "twerk" not in kinds_l:
        _jiggle_cue = (
            r"bounce|bouncing|jiggle|jiggling|jingle|jingling|wobble|sway|"
            r"shake|shaking"
        )
        if not re.search(_jiggle_cue, edit, re.I) or len(edit) < 80:
            edit = (
                "Photorealistic video of the exact woman in the start image: her breasts "
                "bounce, shake, jiggle and sway continuously for the whole clip — clear "
                "soft heavy bounce under the same clothes, natural physics, not frozen and "
                "not a tiny micro-wiggle. Keep her exact same face, hair, expression, "
                "clothes, body proportions, and background; same camera angle and framing; "
                "no jumpcut, no pose swap, no outfit change; sharp face every frame; "
                "one continuous shot"
            )
        elif not re.search(r"bounce, shake, jiggle|jiggle and sway", edit, re.I):
            edit = (
                f"{edit}. Her breasts bounce, shake, jiggle and sway continuously — "
                "clear soft-tissue bounce under the clothes for the whole clip"
            )
        if not re.search(r"no jumpcut|same framing|same (camera )?angle", edit, re.I):
            edit = (
                f"{edit}. Same camera angle and framing as the start image; "
                "no jumpcut, no pose swap"
            )
    # Twerk: same quality pattern with Slow Twerk trigger language.
    if "twerk" in kinds_l:
        _twerk_cue = r"twerk|ass\s*shak|booty|butt\s*(shake|jiggle|bounce)"
        if not re.search(_twerk_cue, edit, re.I) or len(edit) < 80:
            edit = (
                "Photorealistic video of the exact woman in the start image: twerking and "
                "ass shaking — twerks causing her ass to jiggle and shake continuously for "
                "the whole clip, clear heavy booty bounce under the same clothes, natural "
                "physics, not frozen. Keep her exact same face, hair, expression, clothes, "
                "body proportions, and background; same camera angle and framing; no "
                "jumpcut, no pose swap, no outfit change; sharp face every frame; "
                "one continuous shot"
            )
        elif not re.search(r"twerking and ass shaking|ass to jiggle and shake", edit, re.I):
            edit = (
                f"{edit}. Twerking and ass shaking — twerks causing her ass to jiggle "
                "and shake continuously for the whole clip"
            )
        if not re.search(r"no jumpcut|same framing|same (camera )?angle", edit, re.I):
            edit = (
                f"{edit}. Same camera angle and framing as the start image; "
                "no jumpcut, no pose swap"
            )
    # DR34ML4Y AIO trained words (V2) — one pose trigger only, front of prompt.
    _dr34 = {
        "missionary": "m15510n4ry",
        "cowgirl": "c0wg1rl",
        "doggy": "d0gg1e",
        "oral": "bl0wj0b",
        "deepthroat": "bl0wj0b",
    }
    for key in _SEQUENCE_PRIORITY:
        trig = _dr34.get(key)
        if trig and key in kinds_l and not re.search(rf"\b{re.escape(trig)}\b", edit, re.I):
            edit = f"{trig}, {edit}"
            break
    if nsfw and ("oral" in kinds_l or "deepthroat" in kinds_l):
        # Kill jumpcut / kneeling-teleport cues (Blink training trigger) — they
        # break continuity and rewrite the start face.
        edit = re.sub(
            r"(?i)\s*(?:then\s+)?(?<!no )jumpcut\b[^.]*(?:\.|$)",
            ". ",
            edit,
        )
        edit = re.sub(
            r"(?i)\s*kneeling in front of him[^.]*(?:\.|$)",
            ". ",
            edit,
        )
        edit = re.sub(r"\s{2,}", " ", edit).strip(" .")
        # Short / incomplete oral text → one whole self-contained scene prompt
        # (I2V only sees start image + this string — no disconnected fragments).
        _oral_whole = (
            "Photorealistic video of the exact woman in the start image giving a "
            "complete blowjob and deepthroat to one man in this same scene: a man "
            "with visible torso and hips is with her, exactly one erect penis "
            "attached to his body (never floating or detached), she takes that "
            "connected penis fully into her mouth and deepthroats him, then keeps "
            "giving a full continuous blowjob for the entire clip — lips sealed on "
            "the shaft, rhythmic head bobbing, repeated deep in-and-out strokes with "
            "visible full-shaft travel again and again, not tip-only and not frozen. "
            "Keep her exact same face, hair, expression, clothes, and background; "
            "same camera angle and framing; no jumpcut, no kneeling teleport, no "
            "pose swap; sharp face every frame; one continuous shot"
        )
        _has_partner = bool(
            re.search(
                r"\b(man|partner|him|his)\b.*\b(penis|cock|dick)\b|"
                r"\b(penis|cock|dick)\b.*\b(man|partner|attached|connected|torso)\b|"
                r"attached to (his |the )?body|torso and hips",
                edit,
                re.I | re.S,
            )
        )
        _has_act = bool(
            re.search(
                r"deepthroat|continuous blowjob|full(?:y)? (?:into|in) her mouth|"
                r"in-and-out|full[- ]shaft|head bob",
                edit,
                re.I,
            )
        )
        if not (_has_partner and _has_act):
            # Keep LoRA triggers at the front; replace the thin act text with one whole scene.
            leads = []
            if re.search(r"\bbl0wj0b\b", edit, re.I):
                leads.append("bl0wj0b")
            if re.search(r"\bPENISLORA\b", edit, re.I):
                leads.append("PENISLORA")
            lead = (", ".join(leads) + ". ") if leads else ""
            edit = f"{lead}{_oral_whole}"
        elif not re.search(r"no jumpcut|no teleport|same framing|same (camera )?angle", edit, re.I):
            edit = (
                f"{edit}. Same camera angle and framing as the start image; "
                "no jumpcut, no kneeling teleport, no pose swap"
            )
    if nsfw and (
        "penetration" in kinds_l
        or any(k in kinds_l for k in ("missionary", "cowgirl", "doggy"))
    ) and not ("oral" in kinds_l or "deepthroat" in kinds_l):
        pose = next(
            (k for k in ("missionary", "cowgirl", "doggy") if k in kinds_l),
            "missionary",
        )
        _sex_wholes = {
            "missionary": (
                "Photorealistic video of the exact woman in the start image having "
                "missionary sex with one man in this same scene: a man with visible "
                "torso and hips is with her, exactly one erect penis attached to his "
                "body (never floating or detached), he is on top, that connected penis "
                "enters her vagina, then continuous in-and-out thrusting for the entire "
                "clip — full-shaft travel again and again, not frozen and not a tiny "
                "wiggle. Keep her exact same face, hair, expression, and background; "
                "same camera angle and framing; no jumpcut, no pose swap; sharp face "
                "every frame; one continuous shot"
            ),
            "cowgirl": (
                "Photorealistic video of the exact woman in the start image riding "
                "cowgirl on one man in this same scene: a man with visible torso and "
                "hips is with her, exactly one erect penis attached to his body "
                "(never floating or detached), she is on top, that connected penis "
                "is inside her vagina, then continuous riding and thrusting for the "
                "entire clip — full hip travel again and again, not frozen. Keep her "
                "exact same face, hair, expression, and background; same camera angle "
                "and framing; no jumpcut, no pose swap; sharp face every frame; "
                "one continuous shot"
            ),
            "doggy": (
                "Photorealistic video of the exact woman in the start image having "
                "doggy-style sex with one man in this same scene: a man with visible "
                "torso and hips is with her, exactly one erect penis attached to his "
                "body (never floating or detached), he is behind her, that connected "
                "penis enters her vagina, then continuous in-and-out thrusting for the "
                "entire clip — full-shaft travel again and again, not frozen. Keep her "
                "exact same face, hair, expression, and background; same camera angle "
                "and framing; no jumpcut, no pose swap; sharp face every frame; "
                "one continuous shot"
            ),
        }
        _sex_whole = _sex_wholes[pose]
        _has_partner = bool(
            re.search(
                r"\b(man|partner|him|his)\b.*\b(penis|cock|dick)\b|"
                r"\b(penis|cock|dick)\b.*\b(man|partner|attached|connected|torso)\b|"
                r"attached to (his |the )?body|torso and hips",
                edit,
                re.I | re.S,
            )
        )
        _has_act = bool(
            re.search(
                r"continuous thrust|in-and-out|full[- ]shaft|entering her|"
                r"penis (enters|entering)|riding",
                edit,
                re.I,
            )
        )
        if not (_has_partner and _has_act) or len(edit) < 120:
            leads = []
            for trig in ("m15510n4ry", "c0wg1rl", "d0gg1e"):
                if re.search(rf"\b{trig}\b", edit, re.I):
                    leads.append(trig)
            if re.search(r"\bPENISLORA\b", edit, re.I):
                leads.append("PENISLORA")
            lead = (", ".join(leads) + ". ") if leads else ""
            edit = f"{lead}{_sex_whole}"
        elif not re.search(r"no jumpcut|same framing|same (camera )?angle", edit, re.I):
            edit = (
                f"{edit}. Same camera angle and framing as the start image; "
                "no jumpcut, no pose swap"
            )
    if nsfw and "cumshot" in kinds_l:
        # F4C3SPL4SH (K3NK) trained word — required for reliable facial finish.
        if not re.search(r"\bf4c3spl4sh\b", edit, re.I):
            edit = f"f4c3spl4sh, {edit}"
        # Prevent opaque white face-wipe / soft mush from the finish LoRA.
        if not re.search(r"eyes?\s+(stay|remain|visible|readable)|through\s+thinner", edit, re.I):
            edit = (
                f"{edit}. Eyes, brows, and face geometry stay sharp and fully readable "
                "through thinner translucent gel — not an opaque white mask, not soft mush, "
                "not a beauty blur over the whole face"
            )
    edit = edit.rstrip(". ")

    if nsfw:
        oralish = "oral" in kinds_l or "deepthroat" in kinds_l
        sexish = (
            "penetration" in kinds_l
            or any(k in kinds_l for k in ("missionary", "cowgirl", "doggy"))
        )
        if oralish or sexish:
            # Whole oral/sex prompt already describes partner + act + locks.
            # Do not bolt on disconnected Motion:/act: fragments.
            identity = (
                "Exact same woman as the start image — identical face geometry "
                "(eyes, nose, lips, jaw, skin), identical hair; zero face change, "
                "zero beautify, zero morph; natural start expression (no ahegao, "
                "no eye-roll); face razor-sharp every frame. "
            )
            if raw_prompt:
                return f"{identity}{edit}.".strip()
            return f"{identity}User direction: {edit}.".strip()

        identity = (
            "CRITICAL: exact same woman as the start frame — identical face geometry "
            "(eyes, nose, lips, jaw, skin), identical hair; zero face change, zero "
            "beautify, zero morph; keep her natural start expression — no ahegao, "
            "no eye-roll, no cartoon face; face razor-sharp every frame. "
            "Same clothes colors and background. "
        )
        anatomy = (
            "Exactly one erect penis attached to one man's torso and hips — "
            "never floating; continuous sexual action for the full clip. "
        )
        consistency = (
            "ONE continuous shot only — same angle, same framing, no cuts, no jumpcut, "
            "no teleport pose change; stable temporal continuity; "
            "face stays identical and razor-sharp every frame, no soft mush, no beautify."
        )
        if raw_prompt:
            return (
                f"{identity}{edit}. "
                f"Motion: {motion_line} ({amp_phrase}). "
                f"{anatomy}{consistency}"
            ).strip()
        return (
            f"{identity}"
            f"Motion: {motion_line} ({amp_phrase}). "
            f"{anatomy}{consistency} "
            f"User direction: {edit}"
        ).strip()

    consistency = (
        "Stable temporal continuity: single continuous shot, one camera angle, no cuts; "
        "sharp clean photorealistic detail; crisp focus on the face and body; "
        "no soft focus, no motion blur on the face, no smeared skin; "
        "no flicker, no face morphing, no identity drift."
    )
    identity = (
        "CRITICAL identity + scene lock from the start frame: keep the woman's exact face, "
        "eyes, eyebrows, nose, lips, skin tone, hair, body proportions, and likeness "
        "sharp and fully recognizable in every frame; do not age, beautify, blur, soften, "
        "or replace her face; preserve the same background, room, lighting, wardrobe "
        "except clothing removed only when the user asks, camera distance, and framing — "
        "only add the requested action; "
        "her face must stay crisp and readable, never soft or unrecognizable. "
    )
    if raw_prompt:
        return (
            f"{identity}"
            f"{edit}. "
            f"Motion: {motion_line} ({amp_phrase}). "
            f"{consistency} "
            "Continue from the provided start frame with high detail and sharp facial features."
        )
    return (
        "Photorealistic video continuing from the exact provided start frame. "
        f"{identity}"
        "Preserve clothing, body proportions, background, lighting, "
        "and camera framing of the first frame. Do not morph into a different person. "
        f"Motion: {motion_line} ({amp_phrase}). "
        f"{consistency} "
        f"User direction: {edit}"
    )


# Wan I2V requires (length - 1) % 4 == 0. Cap ~5s @16fps (81) for 16GB-class runs.
WAN_LENGTH_MIN = 17  # ~1s @16fps
WAN_LENGTH_MAX = 81  # ~5s @16fps
VIDEO_SECONDS_CHOICES = (2, 3, 4, 5)


def snap_wan_length(raw: int) -> int:
    """Nearest valid Wan frame count in [WAN_LENGTH_MIN, WAN_LENGTH_MAX]."""
    n = max(WAN_LENGTH_MIN, min(WAN_LENGTH_MAX, int(raw)))
    k = round((n - 1) / 4)
    return max(WAN_LENGTH_MIN, min(WAN_LENGTH_MAX, int(k * 4 + 1)))


def frames_for_seconds(seconds: float, fps: int = 16) -> int:
    """Map wall-clock seconds to Wan length at the generation fps."""
    sec = max(1.0, min(float(VIDEO_SECONDS_CHOICES[-1]), float(seconds)))
    fps_i = max(1, int(fps))
    return snap_wan_length(int(round(sec * fps_i)))


def profile_video_params(profile: str) -> dict[str, Any]:
    """Draft–Ultra knobs for video_i2v.v1 (16GB-aware)."""
    table = {
        "draft": {
            "max_side": 480,
            "length": 33,
            "steps": 12,
            "cfg": 3.0,
            "fps": 12,
            "shift": 4.0,
            "post": [],
            "lightx2v": True,  # prefer lighter path when LoRA available
            "expected_runtime_sec": 180,
            "vram_mb": 12000,
        },
        "balanced": {
            "max_side": 640,
            "length": 49,
            "steps": 24,
            "cfg": 3.5,
            "fps": 16,
            "shift": 5.0,
            "post": [],
            "lightx2v": False,
            "expected_runtime_sec": 720,
            "vram_mb": 14000,
        },
        # Default production profile — sharper; length overridden by video_seconds
        "quality": {
            "max_side": 832,
            "length": 81,  # 5s @16fps when UI duration is omitted
            "steps": 42,
            "cfg": 3.5,
            "fps": 16,
            "shift": 5.0,
            "post": [],  # no RIFE — keeps native sharpness
            "lightx2v": False,
            "expected_runtime_sec": 1800,
            "vram_mb": 15500,
        },
        "ultra": {
            "max_side": 832,
            "length": 65,
            "steps": 40,
            "cfg": 3.5,
            "fps": 16,
            "shift": 5.5,
            "post": ["frame_upscale"],
            "lightx2v": False,
            "expected_runtime_sec": 2000,
            "vram_mb": 15500,
        },
    }
    return dict(table.get(profile) or table["balanced"])

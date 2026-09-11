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
    r"\b(cumshot|cum[\s-]?shot|facial|ejaculat)\b",
    re.I,
)

# Pose id → short motion cue (kept tiny — long scaffolds dilute Wan face lock).
POSE_SCAFFOLDS: dict[str, str] = {
    "oral": "continuous blowjob — penis fully in her mouth, slow steady in-and-out head bobbing",
    "deepthroat": "continuous deep oral — penis deep in her mouth, slow steady thrusting",
    "missionary": "missionary thrusting with erect penis in vagina",
    "cowgirl": "cowgirl riding with erect penis in vagina",
    "doggy": "doggy thrusting with erect penis entering from behind",
    "handjob": "hand stroking his erect penis",
    "cumshot": "visible cumshot with man in frame",
    "penetration": "continuous penetrative thrusting",
}

# Kept for tests / callers; NSFW scaffold no longer dumps these (CLIP dilution).
POSE_SEQUENCES: dict[str, str] = {
    "oral": "man appears, she takes his penis fully into her mouth, then continuous blowjob. ",
    "deepthroat": "man appears, she takes him deep, then continuous deep oral. ",
    "missionary": "missionary position, then penetration, then continuous thrusting. ",
    "cowgirl": "cowgirl mount, then penetration, then continuous riding. ",
    "doggy": "doggy position, then penetration, then continuous thrusting. ",
    "handjob": "man appears, then hand grips shaft, then continuous stroking. ",
    "cumshot": "build to climax, then visible cumshot. ",
    "penetration": "penetration begins, then continuous thrusting. ",
}

# Preferred sequence when multiple pose kinds match (most specific first).
_SEQUENCE_PRIORITY = (
    "deepthroat",
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
        # Oral: keep motion readable (not frozen tip-lick) but not jumpcut-fast.
        if "oral" in kinds or "deepthroat" in kinds:
            amplitude = "medium"
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
        amp_phrase = "slow continuous motion, no rush"

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
        if seq and ("oral" in {str(k) for k in kinds} or "deepthroat" in {str(k) for k in kinds}):
            motion_line = f"{seq.strip().rstrip('.')} — {motion_line}"
    else:
        motion_line = "; ".join(kind_bits) if kind_bits else "subtle natural motion"

    edit = (user_prompt or "").strip() or "gentle natural motion"
    if nsfw and "PENISLORA" not in edit.upper():
        # Trigger token for PENISLORA_22 when that LoRA is loaded.
        edit = f"{edit}. PENISLORA"
    kinds_l = [str(k) for k in kinds]
    if nsfw and ("oral" in kinds_l or "deepthroat" in kinds_l):
        # Kill jumpcut / kneeling-teleport cues (Blink training trigger) — they
        # break continuity and rewrite the start face.
        edit = re.sub(
            r"(?i)\s*(?:then\s+)?jumpcut\b[^.]*(?:\.|$)",
            ". ",
            edit,
        )
        edit = re.sub(
            r"(?i)\s*kneeling in front of him[^.]*(?:\.|$)",
            ". ",
            edit,
        )
        edit = re.sub(r"\s{2,}", " ", edit).strip(" .")
        # Partner-enter cue for oral — keep ONE continuous camera (no jumpcut).
        if not re.search(
            r"a man appears and she sucks his (erect )?penis",
            edit,
            re.I,
        ):
            edit = (
                f"{edit}. A man appears and she sucks his penis — "
                "takes him fully into her mouth, then continuous blowjob"
            )
        if not re.search(r"fully into her mouth|continuous blowjob|penis fully in", edit, re.I):
            edit = (
                f"{edit}. Full continuous blowjob sequence: penis fully in her mouth, "
                "lips sealed on the shaft, slow steady head bobbing in and out — "
                "not tip licking only"
            )
        if not re.search(r"no jumpcut|no teleport|same framing|same angle", edit, re.I):
            edit = (
                f"{edit}. Same angle and framing as the start; she stays "
                "in the same standing/portrait pose while performing oral — no jumpcut, "
                "no kneeling teleport, no pose swap"
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
        identity = (
            "CRITICAL: exact same woman as the start frame — identical face geometry "
            "(eyes, nose, lips, jaw, skin), identical hair; zero face change, zero "
            "beautify, zero morph; keep her natural start expression — no ahegao, "
            "no eye-roll, no cartoon face; face razor-sharp every frame. "
            "Same clothes colors and background. "
        )
        anatomy = (
            "Man fully in frame (torso, hips, hands); erect penis clearly visible; "
            "no floating penis, no censored blur. "
        )
        consistency = (
            "ONE continuous shot only — same angle, same framing, no cuts, no jumpcut, "
            "no teleport pose change; stable temporal continuity; "
            "face stays identical and razor-sharp every frame, no soft mush, no beautify."
        )
        # Do not re-dump long sequences — user prompt + LoRA triggers carry the act.
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

"""Wan I2V dual-stage LoRA stack — Core always-on, Optional if present on disk/Comfy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from backend.config import Settings, get_settings

STAGE_STRENGTH_CAP = 4.5
# NSFW prioritizes anatomy LoRAs; allow a slightly fuller stack.
NSFW_STAGE_STRENGTH_CAP = 4.8
LIGHTX2V_STEPS = 8

# Shared Comfy + install-local probe paths (same spirit as edit_runner).
_SHARED_LORAS = Path(r"E:\Comfy-Desktop\ComfyUI-Shared\models\loras")


@dataclass(frozen=True)
class LoraSpec:
    id: str
    stage: str  # "high" | "low"
    strength: float
    files: tuple[str, ...]  # preferred filename first, then aliases
    optional: bool = False
    lightx2v: bool = False
    # Skip on NSFW quality runs (distill LoRAs muddy genital detail).
    skip_on_nsfw: bool = False


# Core package — always attempted (skip if file missing).
# Strengths bias male anatomy + oral; action filter may drop unused ones.
CORE_SPECS: tuple[LoraSpec, ...] = (
    LoraSpec(
        "lightx2v_unc_high",
        "high",
        0.55,
        ("Wan2.2_LightX2V_high_n54vv.safetensors",),
        lightx2v=True,
        skip_on_nsfw=True,
    ),
    LoraSpec(
        "male_gen_high",
        "high",
        0.85,
        ("male_genitalia_enhancer_high.safetensors",),
    ),
    LoraSpec(
        "female_gen_high",
        "high",
        0.85,
        ("female_genitalia_enhancer_high.safetensors",),
    ),
    LoraSpec(
        "penis_lora_high",
        "high",
        1.00,
        (
            "PENISLORA_22_i2v_HIGH_e320.safetensors",
            "PENISLORA_22_i2v_HIGH_e191.safetensors",
        ),
    ),
    LoraSpec(
        "deepthroat_high",
        "high",
        0.65,
        (
            "Wan2.2_I2V_Deepthroat_Blowjob_High.safetensors",
            "jfj-deepthroat-W22-I2V-HN.safetensors",
            "wan22-ultimatedeepthroat-i2v-102epoc-high-k3nk.safetensors",
            "wan22-ultimatedeepthroat-I2V-34epoc-high-k3nk.safetensors",
        ),
    ),
    # Oral Insertion — trigger: "A man appears and she sucks his penis"
    # Forces a real male partner into the frame (not a floating penis).
    LoraSpec(
        "oral_insertion_high",
        "high",
        0.90,
        (
            "Wan2.2_I2V_Oral_Insertion_HIGH.safetensors",
            "wan2.2-i2v-high-oral-insertion-v1.0.safetensors",
        ),
    ),
    LoraSpec(
        "reveal_penis_high",
        "high",
        0.70,
        (
            "Wan2.2_I2V_Reveal_Penis_HIGH.safetensors",
            "Wan2.2-I2V_Reveal_Penis.safetensors",
            "2.2-I2V Reveal Penis_000003000_high_noise.safetensors",
        ),
    ),
    LoraSpec(
        "dr34ml4y_high",
        "high",
        0.45,
        (
            "DR34ML4Y_I2V_14B_HIGH.safetensors",
            "DR34ML4Y_AllInOne.safetensors",
            "wan2.2-i2v-high-dr34ml4y-all-in-one-nsfw.safetensors",
        ),
    ),
    LoraSpec(
        "lightx2v_unc_low",
        "low",
        0.55,
        ("Wan2.2_LightX2V_low_n54vv.safetensors",),
        lightx2v=True,
        skip_on_nsfw=True,
    ),
    LoraSpec(
        "male_gen_low",
        "low",
        0.85,
        ("male_genitalia_enhancer_low.safetensors",),
    ),
    LoraSpec(
        "female_gen_low",
        "low",
        0.85,
        ("female_genitalia_enhancer_low.safetensors",),
    ),
    LoraSpec(
        "penis_lora_low",
        "low",
        0.95,
        (
            "PENISLORA_22_i2v_LOW_e496.safetensors",
            "PENISLORA_22_i2v_LOW.safetensors",
        ),
    ),
    LoraSpec(
        "deepthroat_low",
        "low",
        0.60,
        (
            "Wan2.2_I2V_Deepthroat_Blowjob_Low.safetensors",
            "jfj-deepthroat-W22-I2V-LN.safetensors",
            "wan22-ultimatedeepthroat-I2V-101epoc-low-k3nk.safetensors",
        ),
    ),
    LoraSpec(
        "oral_insertion_low",
        "low",
        0.85,
        (
            "Wan2.2_I2V_Oral_Insertion_LOW.safetensors",
            "wan2.2-i2v-low-oral-insertion-v1.0.safetensors",
        ),
    ),
    LoraSpec(
        "reveal_penis_low",
        "low",
        0.65,
        (
            "Wan2.2_I2V_Reveal_Penis_LOW.safetensors",
            "2.2-I2V Reveal Penis_000003000_low_noise.safetensors",
        ),
    ),
    LoraSpec(
        "cumshot_low",
        "low",
        0.55,
        (
            "Cumshot_LoRA.safetensors",
            "wan22-f4c3spl4sh-154epoc-low-k3nk.safetensors",
        ),
    ),
    LoraSpec(
        "dr34ml4y_low",
        "low",
        0.40,
        (
            "DR34ML4Y_I2V_14B_LOW.safetensors",
            "DR34ML4Y_AllInOne.safetensors",
            "wan2.2-i2v-low-dr34ml4y-all-in-one-nsfw.safetensors",
        ),
    ),
)

# Pose LoRAs — optional; skipped unless matching motion kind is present.
# Preferred names first; Civitai/HF aliases accepted as-found on the GPU box.
OPTIONAL_SPECS: tuple[LoraSpec, ...] = (
    LoraSpec(
        "coachbate_low",
        "low",
        0.60,
        ("CoachBate_PENIS_LoRA.safetensors",),
        optional=True,
    ),
    LoraSpec(
        "smoothmix_low",
        "low",
        0.60,
        ("SmoothMix_Males.safetensors",),
        optional=True,
    ),
    LoraSpec(
        "missionary_high",
        "high",
        0.95,
        (
            "Wan2.2_I2V_Missionary_HIGH.safetensors",
            "Wan2.2 - I2V - Missionary Sex - HIGH 14B.safetensors",
            "Wan2.2-I2V-Missionary-Sex-HIGH14B.safetensors",
            "iGoon_Blink_Missionary_I2V_HIGH v2.safetensors",
            "iGoon - Blink_Missionary_I2V_HIGH.safetensors",
        ),
        optional=True,
    ),
    LoraSpec(
        "missionary_low",
        "low",
        0.90,
        (
            "Wan2.2_I2V_Missionary_LOW.safetensors",
            "Wan2.2 - I2V - Missionary Sex - LOW 14B.safetensors",
            "Wan2.2-I2V-Missionary-Sex-LOW14B.safetensors",
            "iGoon - Blink_Missionary_I2V_LOW v2.safetensors",
            "iGoon_Blink_Missionary_I2V_LOW.safetensors",
        ),
        optional=True,
    ),
    LoraSpec(
        "cowgirl_high",
        "high",
        0.95,
        (
            "Wan2.2_I2V_Cowgirl_HIGH.safetensors",
            "Wan22-I2V-HIGH-Hip_Slammin_Assertive_Cowgirl.safetensors",
            "Wan2.2_Assertive_Cowgirl_I2V_HIGH.safetensors",
            "Assertive_Cowgirl_Wan22_I2V_HIGH.safetensors",
            "wan22_assertive_cowgirl_high.safetensors",
        ),
        optional=True,
    ),
    LoraSpec(
        "cowgirl_low",
        "low",
        0.90,
        (
            "Wan2.2_I2V_Cowgirl_LOW.safetensors",
            "Wan22-I2V-LOW-Hip_Slammin_Assertive_Cowgirl.safetensors",
            "Wan2.2_Assertive_Cowgirl_I2V_LOW.safetensors",
            "Assertive_Cowgirl_Wan22_I2V_LOW.safetensors",
            "wan22_assertive_cowgirl_low.safetensors",
        ),
        optional=True,
    ),
    LoraSpec(
        "doggy_high",
        "high",
        0.95,
        (
            "Wan2.2_I2V_Doggy_HIGH.safetensors",
            "Wan2.2 - I2V - Doggy Style - 14B_high_noise.safetensors",
            "Wan2.2-I2V-DoggyStyle-14B_high_noise.safetensors",
            "Wan2.2_I2V_Doggy_Style_14B_high_noise.safetensors",
            "mql_casting_sex_doggy_kneel_diagonally_behind_vagina_wan22_i2v_v1_high_noise.safetensors",
            "iGoon - Blink_Front_Doggystyle_I2V_HIGH.safetensors",
        ),
        optional=True,
    ),
    LoraSpec(
        "doggy_low",
        "low",
        0.90,
        (
            "Wan2.2_I2V_Doggy_LOW.safetensors",
            "Wan2.2 - I2V - Doggy Style - 14B_low_noise.safetensors",
            "Wan2.2-I2V-DoggyStyle-14B_low_noise.safetensors",
            "Wan2.2_I2V_Doggy_Style_14B_low_noise.safetensors",
            "mql_casting_sex_doggy_kneel_diagonally_behind_vagina_wan22_i2v_v1_low_noise.safetensors",
        ),
        optional=True,
    ),
    LoraSpec(
        "handjob_high",
        "high",
        0.95,
        (
            "Wan2.2_I2V_Handjob_HIGH.safetensors",
            "WAN-2.2-I2V-Handjob-HIGH-v1.safetensors",
            "Wan2.2 - T2V - POV Hand Job - HIGH 14B.safetensors",
            "WAN-2.2-I2V-HandjobBlowjobCombo-HIGH-v1.safetensors",
        ),
        optional=True,
    ),
    LoraSpec(
        "handjob_low",
        "low",
        0.90,
        (
            "Wan2.2_I2V_Handjob_LOW.safetensors",
            "WAN-2.2-I2V-Handjob-LOW-v1.safetensors",
            "Wan2.2 - T2V - POV Hand Job - LOW 14B.safetensors",
            "WAN-2.2-I2V-HandjobBlowjobCombo-LOW-v1.safetensors",
        ),
        optional=True,
    ),
)

# Pose LoRA id prefix → required motion kind (only load when that pose is requested).
_POSE_LORA_KIND: dict[str, str] = {
    "missionary": "missionary",
    "cowgirl": "cowgirl",
    "doggy": "doggy",
    "handjob": "handjob",
}


def _lora_dirs(settings: Settings | None = None) -> list[Path]:
    settings = settings or get_settings()
    dirs: list[Path] = []
    if _SHARED_LORAS.is_dir():
        dirs.append(_SHARED_LORAS)
    root = getattr(settings, "comfyui_dir", None)
    if root:
        p = Path(root) / "models" / "loras"
        if p.is_dir() and p not in dirs:
            dirs.append(p)
    return dirs


def _name_in_available(name: str, available: set[str]) -> Optional[str]:
    """Return the Comfy-facing basename if `name` is listed (path or basename)."""
    if name in available:
        return Path(name).name
    target = Path(name).name.lower()
    for item in available:
        if Path(item).name.lower() == target:
            return Path(item).name
    return None


def _local_lora_path(
    name: str, dirs: list[Path]
) -> Optional[Path]:
    for d in dirs:
        path = d / name
        if path.is_file() and path.stat().st_size > 1000:
            return path
    return None


def _safetensors_readable(path: Path) -> bool:
    """Reject truncated/corrupt .safetensors before Comfy LoraLoaderModelOnly crashes.

    Tiny stubs (unit tests) are accepted without header checks.
    """
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if size <= 1_000_000:
        return size > 1000
    try:
        from safetensors import safe_open

        with safe_open(str(path), framework="pt", device="cpu") as handle:
            return bool(list(handle.keys()))
    except Exception:
        return False


def find_lora_file(
    filenames: tuple[str, ...] | list[str],
    settings: Settings | None = None,
    *,
    available_names: Optional[set[str]] = None,
    trust_remote: bool = True,
) -> Optional[str]:
    """Return the first matching filename that exists on disk or in Comfy's list.

    Production (Render) has no E:\\ models dir — resolve against Comfy
    ``GET /models/loras``. If that list is unavailable/empty and there is no
    local disk, optionally trust the preferred basename so the GPU box still
    loads it (empty catalog previously wiped the entire NSFW stack).

    When a catalog hit also exists locally, the file must open as safetensors
    (Sex crashed on a truncated female_genitalia_enhancer_high).
    """
    settings = settings or get_settings()
    dirs = _lora_dirs(settings)
    catalog = available_names if available_names else None

    if catalog is not None:
        for name in filenames:
            hit = _name_in_available(name, catalog)
            if not hit:
                continue
            local = _local_lora_path(hit, dirs) or _local_lora_path(name, dirs)
            if local is not None and not _safetensors_readable(local):
                # Truncated download — skip so Sex can run without this LoRA.
                continue
            return hit

    for name in filenames:
        path = _local_lora_path(name, dirs)
        if path is None:
            continue
        if not _safetensors_readable(path):
            continue
        return name

    # Remote-only API: never skip core LoRAs just because Render lacks E:\\
    # Treat empty catalog the same as unreachable — tunnel glitches return [].
    if trust_remote and not dirs and catalog is None and filenames:
        return filenames[0]
    return None


def _cap_stage(
    items: list[tuple[str, float, str]],
    cap: float = STAGE_STRENGTH_CAP,
) -> list[tuple[str, float, str]]:
    """Scale strengths so sum(strength) <= cap."""
    total = sum(s for _, s, _ in items)
    if total <= cap or total <= 0:
        return items
    scale = cap / total
    return [(fn, round(s * scale, 4), lid) for fn, s, lid in items]


@dataclass
class ResolvedLoraStack:
    high: list[tuple[str, float]]  # (filename, strength)
    low: list[tuple[str, float]]
    applied_ids: list[str]
    missing_ids: list[str]
    lightx2v_active: bool
    steps_override: Optional[int]

    def label_suffix(self) -> str:
        if not self.applied_ids:
            return ""
        return "loras:" + "+".join(self.applied_ids)

    def to_meta(self) -> dict[str, Any]:
        return {
            "loras_high": [{"file": f, "strength": s} for f, s in self.high],
            "loras_low": [{"file": f, "strength": s} for f, s in self.low],
            "lora_ids": list(self.applied_ids),
            "loras_missing": list(self.missing_ids),
            "lightx2v_active": self.lightx2v_active,
            "steps_override": self.steps_override,
        }


def _action_allows(spec_id: str, kinds: set[str], *, nsfw: bool) -> bool:
    """Drop LoRAs that fight the requested act (keeps strength budget focused)."""
    if not nsfw:
        return True

    oral = "oral" in kinds or "deepthroat" in kinds
    penetration = "penetration" in kinds or any(
        p in kinds for p in ("missionary", "cowgirl", "doggy")
    )
    handjob = "handjob" in kinds
    cumshot = "cumshot" in kinds

    # Pose-specific LoRAs: only when that exact pose kind is present.
    for prefix, need_kind in _POSE_LORA_KIND.items():
        if spec_id.startswith(prefix + "_") or spec_id == prefix:
            return need_kind in kinds

    # Oral Insertion owns partner+penis for oral; Reveal Penis is handjob-only
    # (stacking both with Deepthroat muddy the face and soften detail).
    if spec_id.startswith("oral_insertion"):
        return oral
    # Deepthroat LoRA is aggressive on the face — only when explicitly requested.
    if spec_id.startswith("deepthroat"):
        return "deepthroat" in kinds
    if spec_id.startswith("reveal_penis"):
        return handjob and not oral
    # Male gen enhancer is redundant when PENISLORA + oral insertion are on.
    if oral and not penetration and spec_id.startswith("male_gen"):
        return False

    # Oral-only (no penetration / handjob): skip vagina + finish LoRAs.
    # Also drop generic DR34ML4Y so specialized oral LoRAs keep the strength budget.
    if oral and not penetration and not handjob:
        if spec_id.startswith("female_gen"):
            return False
        if spec_id.startswith("dr34ml4y"):
            return False
        if spec_id == "cumshot_low" and not cumshot:
            return False

    # Penetration-only: skip oral blowjob / oral-insertion LoRAs.
    if penetration and not oral:
        if spec_id.startswith("deepthroat") or spec_id.startswith("oral_insertion"):
            return False

    # Handjob-only: keep penis LoRAs; drop oral + female gen + finish noise.
    if handjob and not oral and not penetration:
        if spec_id.startswith("deepthroat") or spec_id.startswith("oral_insertion"):
            return False
        if spec_id.startswith("female_gen"):
            return False
        if spec_id == "cumshot_low" and not cumshot:
            return False

    # Cumshot LoRA only when finish is explicitly requested (not all Sex runs).
    if spec_id == "cumshot_low":
        return cumshot

    return True


def resolve_video_lora_stack(
    settings: Settings | None = None,
    *,
    include_optional: bool = True,
    available_names: Optional[set[str]] = None,
    trust_remote: bool = True,
    nsfw: bool = False,
    motion_kinds: Optional[list[str]] = None,
) -> ResolvedLoraStack:
    """
    Resolve Core (+ Optional if present) against Comfy list and/or local disk.

    Missing files are skipped. Per-stage strength capped (higher for NSFW).
    LightX2V distill LoRAs are omitted on NSFW runs so anatomy LoRAs dominate.
    """
    settings = settings or get_settings()
    specs = list(CORE_SPECS)
    if include_optional:
        specs.extend(OPTIONAL_SPECS)
    kinds = {str(k) for k in (motion_kinds or [])}

    high_raw: list[tuple[str, float, str]] = []
    low_raw: list[tuple[str, float, str]] = []
    applied: list[str] = []
    missing: list[str] = []
    lightx2v_ids: set[str] = set()

    for spec in specs:
        if nsfw and spec.skip_on_nsfw:
            continue
        if not _action_allows(spec.id, kinds, nsfw=nsfw):
            continue
        found = find_lora_file(
            spec.files,
            settings,
            available_names=available_names,
            trust_remote=trust_remote and not spec.optional,
        )
        if not found:
            if not spec.optional:
                missing.append(spec.id)
            continue
        applied.append(spec.id)
        entry = (found, float(spec.strength), spec.id)
        if spec.stage == "high":
            high_raw.append(entry)
        else:
            low_raw.append(entry)
        if spec.lightx2v:
            lightx2v_ids.add(spec.id)

    cap = NSFW_STAGE_STRENGTH_CAP if nsfw else STAGE_STRENGTH_CAP
    high_capped = _cap_stage(high_raw, cap)
    low_capped = _cap_stage(low_raw, cap)
    high = [(fn, s) for fn, s, _ in high_capped]
    low = [(fn, s) for fn, s, _ in low_capped]

    lightx2v_active = (
        "lightx2v_unc_high" in applied and "lightx2v_unc_low" in applied
    )
    # Distill LoRAs are kept as a mild uncensored nudge. Do NOT force 8-step
    # sampling on quality runs — that kills anatomy detail vs HF Spaces.
    # Callers may still opt into LIGHTX2V_STEPS for draft profiles.
    steps_override = None

    return ResolvedLoraStack(
        high=high,
        low=low,
        applied_ids=applied,
        missing_ids=missing,
        lightx2v_active=lightx2v_active,
        steps_override=steps_override,
    )

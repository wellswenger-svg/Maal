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
# Staged / secondary weights — delete models/loras/miscellaneous/ when retiring.
MISC_SUBDIR = "miscellaneous"


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
    # iGOON Blink Blowjob — full-sequence continuity (no jumpcut).
    # 0.65 OOMs/dies on tunnel; 0.55 + 5s (+ mild DR34) is the full-BJ path.
    LoraSpec(
        "deepthroat_high",
        "high",
        0.55,
        (
            "Wan2.2_I2V_Blink_Blowjob_HIGH.safetensors",
            "iGOON_Blink_Blowjob_I2V_HIGH.safetensors",
        ),
    ),
    # F4C3SPL4SH (K3NK) — facial cumshot; trigger f4c3spl4sh.
    # Author used 1.0/1.4 but that wipes face identity — bias readable eyes/face.
    LoraSpec(
        "cumshot_high",
        "high",
        0.70,
        (
            "Wan2.2_I2V_Cumshot_HIGH.safetensors",
            "wan22-f4c3spl4sh-100epoc-high-k3nk.safetensors",
            "Cumshot_LoRA_HIGH.safetensors",
        ),
    ),
    # DR34ML4Y AIO — BJ/missionary/cowgirl/doggy in one LoRA. Prefer V2.
    LoraSpec(
        "dr34ml4y_high",
        "high",
        0.45,
        (
            "DR34ML4Y_I2V_14B_HIGH_V2.safetensors",
            f"{MISC_SUBDIR}/DR34ML4Y_I2V_14B_HIGH.safetensors",
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
        0.50,
        (
            "Wan2.2_I2V_Blink_Blowjob_LOW.safetensors",
            "iGOON_Blink_Blowjob_I2V_LOW.safetensors",
        ),
    ),
    LoraSpec(
        "cumshot_low",
        "low",
        0.95,
        (
            "Cumshot_LoRA.safetensors",
            "Wan2.2_I2V_Cumshot_LOW.safetensors",
            "wan22-f4c3spl4sh-154epoc-low-k3nk.safetensors",
        ),
    ),
    LoraSpec(
        "dr34ml4y_low",
        "low",
        0.40,
        (
            "DR34ML4Y_I2V_14B_LOW_V2.safetensors",
            f"{MISC_SUBDIR}/DR34ML4Y_I2V_14B_LOW.safetensors",
            "DR34ML4Y_I2V_14B_LOW.safetensors",
            "DR34ML4Y_AllInOne.safetensors",
            "wan2.2-i2v-low-dr34ml4y-all-in-one-nsfw.safetensors",
        ),
    ),
)

# Pose LoRAs — optional; loaded when freeform text / Sex button sets that motion kind.
OPTIONAL_SPECS: tuple[LoraSpec, ...] = (
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

# Misc / staged-for-removal — files live under models/loras/miscellaneous/.
# Wired for remote text-box use; delete the folder when retiring these.
MISC_SPECS: tuple[LoraSpec, ...] = (
    LoraSpec(
        "oral_insertion_high",
        "high",
        0.90,
        (
            f"{MISC_SUBDIR}/Wan2.2_I2V_Oral_Insertion_HIGH.safetensors",
            "Wan2.2_I2V_Oral_Insertion_HIGH.safetensors",
        ),
        optional=True,
    ),
    LoraSpec(
        "oral_insertion_low",
        "low",
        0.85,
        (
            f"{MISC_SUBDIR}/Wan2.2_I2V_Oral_Insertion_LOW.safetensors",
            "Wan2.2_I2V_Oral_Insertion_LOW.safetensors",
        ),
        optional=True,
    ),
    LoraSpec(
        "reveal_penis_high",
        "high",
        0.90,
        (
            f"{MISC_SUBDIR}/Wan2.2_I2V_Reveal_Penis_HIGH.safetensors",
            "Wan2.2_I2V_Reveal_Penis_HIGH.safetensors",
        ),
        optional=True,
    ),
    LoraSpec(
        "reveal_penis_low",
        "low",
        0.85,
        (
            f"{MISC_SUBDIR}/Wan2.2_I2V_Reveal_Penis_LOW.safetensors",
            "Wan2.2_I2V_Reveal_Penis_LOW.safetensors",
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
    "oral_insertion": "oral_insertion",
    "reveal_penis": "reveal_penis",
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
    """Return the Comfy-facing path (may include miscellaneous/)."""
    name_norm = name.replace("\\", "/")
    if name_norm in available:
        return name_norm
    # Also accept Windows-style catalog entries.
    if name_norm.replace("/", "\\") in available:
        return name_norm
    target = Path(name_norm).name.lower()
    preferred: Optional[str] = None
    for item in available:
        item_n = item.replace("\\", "/")
        if Path(item_n).name.lower() != target:
            continue
        # Prefer subfolder path so LoraLoader can find moved misc weights.
        if preferred is None or ("/" in item_n and "/" not in preferred):
            preferred = item_n
    return preferred


def _local_lora_path(name: str, dirs: list[Path]) -> Optional[Path]:
    name_norm = name.replace("\\", "/")
    base = Path(name_norm).name
    for d in dirs:
        for candidate in (
            d / name_norm,
            d / MISC_SUBDIR / base,
            d / base,
        ):
            if candidate.is_file() and candidate.stat().st_size > 1000:
                return candidate
    return None


def _comfy_rel_from_local(path: Path, dirs: list[Path]) -> str:
    """Map a local path to the Comfy lora_name (subdirectory-aware)."""
    for d in dirs:
        try:
            return path.relative_to(d).as_posix()
        except ValueError:
            continue
    return path.name


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
        return _comfy_rel_from_local(path, dirs)

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

    # Oral insertion (misc): skip Blink so tip-in LoRA owns the motion.
    if "oral_insertion" in kinds and spec_id.startswith("deepthroat"):
        return False

    # Oral BJ full-sequence: Blink drives bobbing; DR34ML4Y V2 adds partner body.
    if spec_id.startswith("deepthroat"):
        return oral
    # Male gen enhancer is redundant when PENISLORA is on for oral-only.
    if oral and not penetration and spec_id.startswith("male_gen"):
        return False

    # Oral-only (no penetration / handjob): skip vagina + finish LoRAs.
    # Keep Blink + DR34 (gold motion @ 5s + V2 partner cue).
    if oral and not penetration and not handjob:
        if spec_id.startswith("female_gen"):
            return False
        if spec_id.startswith("cumshot") and not cumshot:
            return False

    # Penetration-only: skip oral blowjob LoRAs.
    if penetration and not oral:
        if spec_id.startswith("deepthroat"):
            return False

    # Handjob-only: keep penis LoRAs; drop oral + female gen + finish noise.
    if handjob and not oral and not penetration:
        if spec_id.startswith("deepthroat"):
            return False
        if spec_id.startswith("female_gen"):
            return False
        if spec_id.startswith("cumshot") and not cumshot:
            return False

    # Cumshot-only facial finish: drop vagina + generic dream so Cumshot + PENISLORA
    # keep the strength budget (same idea as oral-only). Keep male_gen for partner.
    if cumshot and not oral and not penetration and not handjob:
        if spec_id.startswith("female_gen"):
            return False
        if spec_id.startswith("dr34ml4y"):
            return False

    # Cumshot LoRA only when finish is explicitly requested (not all Sex runs).
    if spec_id.startswith("cumshot"):
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
        specs.extend(MISC_SPECS)
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
        strength = float(spec.strength)
        oral = "oral" in kinds or "deepthroat" in kinds
        penetration = "penetration" in kinds or any(
            p in kinds for p in ("missionary", "cowgirl", "doggy")
        )
        # Oral + Blink + DR34: soften PENISLORA/DR34 so they don't invent a 2nd shaft.
        if nsfw and oral and not penetration:
            if spec.id.startswith("penis_lora"):
                strength = min(strength, 0.82 if spec.stage == "high" else 0.78)
            elif spec.id.startswith("dr34ml4y"):
                strength = min(strength, 0.32 if spec.stage == "high" else 0.28)
        entry = (found, strength, spec.id)
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

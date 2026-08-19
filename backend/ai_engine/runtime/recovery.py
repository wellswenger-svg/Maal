"""Error recovery: OOM degrade, retries, fallback workflows, corrupt output, queue/timeout."""

from __future__ import annotations

import asyncio
import re
from typing import Any, Optional

from backend.ai_engine.runtime import vram

# Max attempts per stage (same workflow+profile), then degrade/fallback.
MAX_RETRIES = 2

_OOM_PATTERNS = re.compile(
    r"(out of memory|cuda.?oom|cudnn_status_alloc_failed|hip.?out.?of.?memory|"
    r"resource exhausted|failed to allocate|oom\b)",
    re.I,
)
_TIMEOUT_PATTERNS = re.compile(
    r"(timed?\s*out|timeout|deadline exceeded)",
    re.I,
)
_TRANSIENT_PATTERNS = re.compile(
    r"(connection reset|connection closed|no close frame|temporarily unavailable|"
    r"503|broken pipe|websocket|ConnectionClosed)",
    re.I,
)


def record(
    events: list[dict[str, Any]],
    *,
    kind: str,
    detail: str,
    action: str,
    **extra: Any,
) -> None:
    ev: dict[str, Any] = {"kind": kind, "detail": detail, "action": action}
    ev.update(extra)
    events.append(ev)


def next_profile_down(profile: str) -> Optional[str]:
    order = ["ultra", "quality", "balanced", "draft"]
    if profile not in order:
        return "draft"
    idx = order.index(profile)
    if idx >= len(order) - 1:
        return None
    return order[idx + 1]


def classify_error(exc: BaseException) -> str:
    msg = str(exc)
    if _OOM_PATTERNS.search(msg) or type(exc).__name__ in (
        "OutOfMemoryError",
        "CUDAOutOfMemoryError",
    ):
        return "oom"
    if _TIMEOUT_PATTERNS.search(msg):
        return "timeout"
    if _TRANSIENT_PATTERNS.search(msg):
        return "transient"
    if "CORRUPT_OUTPUT" in msg:
        return "corrupt"
    if "MODEL_UNAVAILABLE" in msg or "MODEL_MISSING" in msg:
        return "model"
    return "other"


def is_corrupt_output(data: Optional[bytes], *, min_bytes: int = 32) -> bool:
    if data is None:
        return True
    if len(data) < min_bytes:
        return True
    # Reject all-null buffers
    if data[:64] == b"\x00" * min(64, len(data)):
        return True
    return False


async def backoff(attempt: int, *, base_sec: float = 0.35) -> None:
    """Bounded jitter-free backoff for transient Comfy disconnects."""
    delay = base_sec * (2 ** max(0, attempt - 1))
    delay = min(delay, 3.0)
    await asyncio.sleep(delay)


def recover_oom(events: list[dict[str, Any]], profile: str) -> Optional[str]:
    """Unload VRAM and propose a lower profile. Returns new profile or None."""
    info = vram.release_stage("oom_recovery")
    nxt = next_profile_down(profile)
    record(
        events,
        kind="oom",
        detail=f"profile={profile}",
        action=f"degrade_to:{nxt}" if nxt else "abort",
        vram=info,
    )
    return nxt


def recover_after_failure(
    events: list[dict[str, Any]],
    exc: BaseException,
    *,
    profile: str,
    attempt: int,
    fallback_workflow_ref: Optional[str],
) -> dict[str, Any]:
    """
    Decide next action after a runner failure.

    Returns dict with keys:
      action: retry | degrade | fallback | abort
      profile: maybe updated
      fallback_ref: optional
    """
    kind = classify_error(exc)
    detail = f"{type(exc).__name__}: {exc}"

    if kind == "oom":
        nxt = recover_oom(events, profile)
        if nxt:
            return {"action": "degrade", "profile": nxt, "fallback_ref": None}
        if fallback_workflow_ref:
            record(
                events,
                kind="oom",
                detail=detail,
                action=f"fallback:{fallback_workflow_ref}",
            )
            return {
                "action": "fallback",
                "profile": "draft",
                "fallback_ref": fallback_workflow_ref,
            }
        record(events, kind="oom", detail=detail, action="abort")
        return {"action": "abort", "profile": profile, "fallback_ref": None}

    if kind in ("transient", "timeout") and attempt < MAX_RETRIES:
        vram.release_stage(f"after_{kind}")
        record(
            events,
            kind=kind,
            detail=detail,
            action=f"retry:{attempt + 1}",
            attempt=attempt,
        )
        return {"action": "retry", "profile": profile, "fallback_ref": None}

    if kind == "corrupt" and attempt < MAX_RETRIES:
        record(
            events,
            kind="corrupt_output",
            detail=detail,
            action=f"retry:{attempt + 1}",
            attempt=attempt,
        )
        return {"action": "retry", "profile": profile, "fallback_ref": None}

    if fallback_workflow_ref and kind in ("other", "model", "timeout", "corrupt"):
        record(
            events,
            kind=kind,
            detail=detail,
            action=f"fallback:{fallback_workflow_ref}",
        )
        return {
            "action": "fallback",
            "profile": profile,
            "fallback_ref": fallback_workflow_ref,
        }

    record(events, kind=kind, detail=detail, action="abort")
    return {"action": "abort", "profile": profile, "fallback_ref": None}

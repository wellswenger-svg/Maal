"""VRAM stage helpers — sequential load/unload for RTX 5060 Ti 16GB."""

from __future__ import annotations

import gc
import logging
from typing import Any

log = logging.getLogger(__name__)


def release_stage(reason: str = "") -> dict[str, Any]:
    """Best-effort free CPU + CUDA cache between planner/perception/gen/post."""
    gc.collect()
    freed = False
    reserved_before = None
    reserved_after = None
    try:
        import torch

        if torch.cuda.is_available():
            try:
                reserved_before = int(torch.cuda.memory_reserved(0))
            except Exception:
                pass
            torch.cuda.empty_cache()
            try:
                torch.cuda.ipc_collect()
            except Exception:
                pass
            gc.collect()
            torch.cuda.empty_cache()
            freed = True
            try:
                reserved_after = int(torch.cuda.memory_reserved(0))
            except Exception:
                pass
    except Exception as exc:
        log.debug("vram release skipped: %s", exc)
    return {
        "stage_release": reason or "generic",
        "cuda_empty_cache": freed,
        "reserved_before": reserved_before,
        "reserved_after": reserved_after,
    }

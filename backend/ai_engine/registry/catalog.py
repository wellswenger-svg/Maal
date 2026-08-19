"""Register all workflow modules into the process registry."""

from __future__ import annotations

from backend.ai_engine.ops.scorecard import apply_scorecards
from backend.ai_engine.workflows.background_remove import v1 as bg_remove
from backend.ai_engine.workflows.edit_suite import v1 as edit_suite
from backend.ai_engine.workflows.experimental import stubs as experimental_stubs
from backend.ai_engine.workflows.image_img2img import v0_legacy as img_legacy
from backend.ai_engine.workflows.video_i2v import v0_legacy as vid_legacy
from backend.ai_engine.workflows.video_i2v import v1 as vid_v1

_bootstrapped = False


def bootstrap_workflows(*, force: bool = False) -> None:
    """
    Idempotent by default so tests can patch runners without re-register wiping them.
    Pass force=True after adding new workflow modules in a long-lived process.
    """
    global _bootstrapped
    if _bootstrapped and not force:
        return
    img_legacy.register()
    vid_legacy.register()
    vid_v1.register()
    bg_remove.register()
    edit_suite.register()
    experimental_stubs.register()
    apply_scorecards()
    _bootstrapped = True

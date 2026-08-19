"""Phase 5 post tests. Graphic fixtures load from gitignored private/tests."""

from backend.ai_engine.runtime_overlay import attach_private_tests

attach_private_tests(globals(), "test_phase5_edits.py")

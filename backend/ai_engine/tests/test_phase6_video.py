"""Phase 6 video tests. Graphic fixtures load from gitignored private/tests."""

from backend.ai_engine.runtime_overlay import attach_private_tests

attach_private_tests(globals(), "test_phase6_video.py")

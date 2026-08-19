"""Test-mode helpers."""

from __future__ import annotations

import unittest

from backend.test_mode import normalize_preset_id, review_bin_map


class TestTestMode(unittest.TestCase):
    def test_normalize_preset_id(self) -> None:
        self.assertEqual(normalize_preset_id("Enhance"), "enhance")
        self.assertEqual(normalize_preset_id("style_edit"), "style_edit")
        with self.assertRaises(ValueError):
            normalize_preset_id("Not Valid!")

    def test_review_bin_map_is_dict(self) -> None:
        self.assertIsInstance(review_bin_map(), dict)

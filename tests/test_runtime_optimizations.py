"""Regression tests for the graph and algorithm optimizations.

Run with: python -m unittest discover -s tests -v
"""
import math
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import algorithm
from graph_fast import FastGraph


class GraphColorOptimizationTests(unittest.TestCase):
    @staticmethod
    def make_graph():
        # Avoid opening a Tk window: only set_color's internal state is needed.
        graph = FastGraph.__new__(FastGraph)
        graph._color_rgb = (255, 90, 90)
        graph._played_fill_rgb = (115, 41, 41)
        graph._played_stroke_rgb = (216, 76, 76)
        graph._poly_data = object()
        graph._last_split_px = 17
        graph._rebuild_images = Mock()
        return graph

    def test_repeated_color_does_not_rebuild_images(self):
        graph = self.make_graph()
        graph.set_color("#ff5a5a")
        graph.set_color("#FF5A5A")

        graph._rebuild_images.assert_not_called()
        self.assertEqual(graph._last_split_px, 17)

    def test_new_color_rebuilds_images_and_resets_cursor(self):
        graph = self.make_graph()
        graph.set_color("#00ffd5")

        graph._rebuild_images.assert_called_once_with()
        self.assertEqual(graph._color_rgb, (0, 255, 213))
        self.assertEqual(graph._last_split_px, -1)

        graph.set_color("#00FFD5")
        graph._rebuild_images.assert_called_once_with()

    def test_color_changes_without_graph_data_do_not_render(self):
        graph = self.make_graph()
        graph._poly_data = None
        graph.set_color("#ffd84d")

        graph._rebuild_images.assert_not_called()
        self.assertEqual(graph._color_rgb, (255, 216, 77))


class AlgorithmOptimizationTests(unittest.TestCase):
    def test_calculation_computes_corners_once(self):
        # A representative 4K chart with all four columns populated.
        notes = [(i % 4, 1000 + i * 180) for i in range(80)]
        original = algorithm.get_corners

        with patch.object(algorithm, "get_corners", wraps=original) as get_corners:
            sr, times, strain, factors = algorithm.calculate_notes(
                notes, keycount=4, od=9
            )

        get_corners.assert_called_once()
        self.assertTrue(math.isfinite(sr))
        self.assertEqual(len(times), len(strain))
        self.assertIn("Pressing Intensity", factors)


if __name__ == "__main__":
    unittest.main()

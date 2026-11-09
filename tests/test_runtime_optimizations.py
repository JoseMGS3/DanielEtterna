"""Regression tests for the graph and algorithm optimizations.

Run with: python -m unittest discover -s tests -v
"""
import math
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

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
        graph._visible = True
        graph._images_dirty = False
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




class HiddenGraphRenderingTests(unittest.TestCase):
    def make_graph(self):
        canvas = Mock()
        canvas.create_image.return_value = 1
        with patch("graph_fast.tk.PhotoImage") as photo_type:
            graph = FastGraph(canvas, 80, 160)
        photo = photo_type.return_value
        graph._build_polygon = Mock(return_value=([[]], [[]]))

        def provide_cached_images():
            graph._played_rgb = np.zeros((80, 160, 3), dtype=np.uint8)
            graph._unplayed_rgb = np.ones((80, 160, 3), dtype=np.uint8)
            graph._composite_rgb = np.empty((80, 160, 3), dtype=np.uint8)

        graph._rebuild_images = Mock(side_effect=provide_cached_images)
        return graph, canvas, photo

    def test_hidden_layout_defers_chart_color_and_cursor_rendering(self):
        graph, canvas, photo = self.make_graph()
        graph.hide()
        graph.set_data([0, 1000, 2000], [1, 2, 3])
        graph.set_color("#00ffd5")
        graph.update_position(1500, "NM")

        graph._build_polygon.assert_not_called()
        graph._rebuild_images.assert_not_called()
        photo.configure.assert_not_called()
        self.assertEqual(graph._last_position, (1500, "NM"))

        graph.show()
        graph._build_polygon.assert_called_once_with()
        graph._rebuild_images.assert_called_once_with()
        photo.configure.assert_called_once()
        self.assertEqual(graph._color_rgb, (0, 255, 213))
        self.assertEqual(canvas.itemconfigure.call_args.kwargs["state"], "normal")

        graph.show()
        graph._rebuild_images.assert_called_once_with()
        photo.configure.assert_called_once()

    def test_hidden_color_change_rebuilds_only_when_shown(self):
        graph, _canvas, photo = self.make_graph()
        graph.set_data([0, 1000, 2000], [1, 2, 3])
        self.assertEqual(graph._rebuild_images.call_count, 1)
        graph.update_position(500, "NM")
        self.assertEqual(photo.configure.call_count, 1)

        graph.hide()
        graph.set_color("#ffd84d")
        graph.update_position(1700, "NM")
        self.assertEqual(graph._rebuild_images.call_count, 1)
        self.assertEqual(photo.configure.call_count, 1)

        graph.show()
        self.assertEqual(graph._rebuild_images.call_count, 2)
        self.assertEqual(photo.configure.call_count, 2)
        self.assertEqual(graph._last_position, (1700, "NM"))

    def test_hidden_multiple_charts_only_render_most_recent(self):
        graph, _canvas, _photo = self.make_graph()
        graph.hide()
        graph.set_data([0, 100, 200], [1, 1, 1])
        graph.set_data([0, 200, 400], [2, 2, 2])
        graph.update_position(300, "NM")
        graph._build_polygon.assert_not_called()

        graph.show()
        graph._build_polygon.assert_called_once_with()
        graph._rebuild_images.assert_called_once_with()
        self.assertEqual(graph._t_max, 400.0)

    def test_hidden_without_data_never_renders_image(self):
        graph, _canvas, photo = self.make_graph()
        graph.hide()
        graph.update_position(500)
        graph.set_color("#00ffd5")
        graph.show()

        graph._rebuild_images.assert_not_called()
        photo.configure.assert_not_called()


if __name__ == "__main__":
    unittest.main()

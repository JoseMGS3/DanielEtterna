"""Regression tests for DanielEtterna v1.1.1 geometry configuration."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import config_manager


class MainWindowConfigTests(unittest.TestCase):
    def test_upgrade_from_v11_adds_default_per_layout_sizes(self):
        old = {"config_version": 6, "layout": "statistics"}
        merged = config_manager._merge_defaults(old)
        self.assertEqual(merged["config_version"], 8)
        self.assertEqual(merged["layout"], "statistics")
        self.assertEqual(merged["window_sizes"], {
            "compact": {"width": 550, "height": 72},
            "statistics": {"width": 650, "height": 116},
            "full": {"width": 650, "height": 407},
        })
        self.assertEqual(merged["main_window_geometry"], "")

    def test_preserves_each_layout_and_screen_position(self):
        settings = {
            "config_version": 7,
            "layout": "full",
            "main_window_geometry": "800x450+-1920+108",
            "window_sizes": {
                "compact": {"width": 375, "height": 74},
                "statistics": {"width": 500, "height": 120},
                "full": {"width": 800, "height": 450},
            },
        }
        merged = config_manager._merge_defaults(settings)
        self.assertEqual(merged["main_window_geometry"], "800x450+-1920+108")
        self.assertEqual(merged["window_sizes"], settings["window_sizes"])

    def test_clamps_dimensions_to_half_of_default(self):
        merged = config_manager._merge_defaults({
            "window_sizes": {
                "compact": {"width": 1, "height": 1},
                "statistics": {"width": 1, "height": 1},
                "full": {"width": 1, "height": 1},
            }
        })
        self.assertEqual(merged["window_sizes"], {
            "compact": {"width": 275, "height": 36},
            "statistics": {"width": 325, "height": 58},
            "full": {"width": 325, "height": 204},
        })

    def test_migrates_old_compact_preset_and_geometry(self):
        merged = config_manager._merge_defaults({
            "config_version": 7,
            "layout": "compact",
            "main_window_geometry": "550x102+120+200",
            "window_sizes": {
                "compact": {"width": 550, "height": 102},
                "statistics": {"width": 488, "height": 118},
                "full": {"width": 650, "height": 407},
            },
        })
        self.assertEqual(merged["main_window_geometry"], "550x72+120+200")
        self.assertEqual(merged["window_sizes"]["compact"]["height"], 72)
        self.assertEqual(merged["window_sizes"]["statistics"]["height"], 87)

    def test_migrates_old_statistics_geometry_preserving_monitor_position(self):
        merged = config_manager._merge_defaults({
            "config_version": 7,
            "layout": "statistics",
            "main_window_geometry": "650x157+-1920+108",
        })
        self.assertEqual(merged["main_window_geometry"], "650x116+-1920+108")

    def test_preserves_custom_sizes_when_migrating(self):
        merged = config_manager._merge_defaults({
            "config_version": 7,
            "layout": "compact",
            "main_window_geometry": "490x85+125+250",
            "window_sizes": {
                "compact": {"width": 490, "height": 85},
                "statistics": {"width": 510, "height": 125},
            },
        })
        self.assertEqual(merged["main_window_geometry"], "490x85+125+250")
        self.assertEqual(merged["window_sizes"]["compact"]["height"], 85)
        self.assertEqual(merged["window_sizes"]["statistics"]["height"], 125)

    def test_save_and_reload_main_window_size(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            cfg = config_manager._merge_defaults({
                "layout": "compact",
                "main_window_geometry": "366x85+125+250",
                "window_sizes": {
                    "compact": {"width": 366, "height": 85},
                    "statistics": {"width": 488, "height": 118},
                    "full": {"width": 650, "height": 407},
                },
            })
            with patch.object(config_manager, "get_config_path", return_value=path):
                config_manager.save_config(cfg)
                recovered = config_manager.load_config()
            self.assertEqual(recovered["main_window_geometry"], "366x85+125+250")
            self.assertEqual(recovered["window_sizes"], cfg["window_sizes"])


if __name__ == "__main__":
    unittest.main()

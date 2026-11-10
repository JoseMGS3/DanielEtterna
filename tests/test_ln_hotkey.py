"""Regression tests for the configurable XDC1 LN toggle."""
import ast
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import config_manager
import i18n


class LongNoteHotkeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "src" / "daniel_etterna.py").read_text(
            encoding="utf-8",
        )
        cls.tree = ast.parse(cls.source)

    @classmethod
    def extract_functions(cls, *names):
        funcs = [
            node for node in cls.tree.body
            if isinstance(node, ast.FunctionDef) and node.name in names
        ]
        assert len(funcs) == len(names)
        return compile(
            ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[])),
            "<LN toggle extracted from UI>", "exec",
        )

    def test_default_and_old_config_migration(self):
        self.assertEqual(config_manager.DEFAULT_CONFIG["keybinds"]["toggle_lns"], "L")
        self.assertTrue(config_manager.DEFAULT_CONFIG["include_long_notes"])
        old = config_manager._merge_defaults({
            "config_version": 9,
            "difficulty_engine": "XDC1",
            "keybinds": {
                "toggle_topmost": "F2",
                "cycle_mode": "Tab",
                "open_settings": "Q",
            },
        })
        self.assertEqual(old["keybinds"]["toggle_lns"], "L")
        self.assertEqual(old["keybinds"]["toggle_topmost"], "F2")
        self.assertTrue(old["include_long_notes"])
        self.assertFalse(config_manager._merge_defaults({
            "include_long_notes": False,
        })["include_long_notes"])
        self.assertTrue(config_manager._merge_defaults({
            "include_long_notes": "False",
        })["include_long_notes"])

    def test_ln_setting_and_custom_keybind_persist(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(config_manager, "get_config_dir",
                              return_value=Path(folder)):
                config = config_manager._merge_defaults({
                    "include_long_notes": False,
                    "keybinds": {"toggle_lns": "Ctrl+L"},
                })
                config_manager.save_config(config)
                loaded = config_manager.load_config()
        self.assertFalse(loaded["include_long_notes"])
        self.assertEqual(loaded["keybinds"]["toggle_lns"], "Ctrl+L")
        self.assertEqual(config_manager.keybind_to_tk("L"), "<l>")
        self.assertEqual(config_manager.keybind_to_tk("Ctrl+L"), "<Control-l>")

    def test_toggle_recalculates_and_disallows_stale_result_after_double_tap(self):
        config = {"difficulty_engine": "XDC1", "include_long_notes": True}
        graph, update, manager = Mock(), Mock(), Mock()
        scope = {
            "APP_CONFIG": config,
            "lock": threading.RLock(),
            "_ln_toggle_revision": 0,
            "last_state": ("cached",),
            "_last_sr": 14.2,
            "_last_dan_label": "Mid-Delta",
            "_last_dan_numeric": 14.5,
            "current_msd_data": {"overall": 14.2},
            "current_strain_data": ([0, 1], [1, 2]),
            "current_map": "chart.ssc",
            "current_difficulty": "Hard",
            "current_meter": "17",
            "current_description": "",
            "current_stepstype": "dance-single",
            "current_rate": 1.0,
            "graph": graph,
            "update_dan_text": update,
            "config_manager": manager,
        }
        exec(self.extract_functions(
            "toggle_long_notes", "_calculation_snapshot",
        ), scope)
        original = scope["_calculation_snapshot"]()
        self.assertEqual(original[-2:], (True, 0))
        self.assertEqual(scope["toggle_long_notes"](), "break")
        first = scope["_calculation_snapshot"]()
        self.assertEqual(first[-2:], (False, 1))
        self.assertIsNone(scope["last_state"])
        self.assertIsNone(scope["_last_sr"])
        self.assertIsNone(scope["current_strain_data"])
        graph.hide.assert_called_once()
        update.assert_called_once_with(".", "")
        manager.save_config.assert_called_once_with(config)

        self.assertEqual(scope["toggle_long_notes"](), "break")
        second = scope["_calculation_snapshot"]()
        self.assertEqual(second[-2:], (True, 2))
        self.assertNotEqual(original, second)
        self.assertNotEqual(first, second)

        config["difficulty_engine"] = "Legacy"
        graph.reset_mock()
        self.assertEqual(scope["toggle_long_notes"](), "break")
        graph.hide.assert_not_called()
        self.assertEqual(scope["_ln_toggle_revision"], 2)

    def test_keybind_is_shown_in_options_and_wired_locally_and_globally(self):
        source = self.source
        self.assertIn('"toggle_lns": toggle_long_notes', source)
        self.assertIn('tr("toggle_lns")', source)
        self.assertIn("global _local_ln_keycode", source)
        self.assertIn('"<KeyRelease>"', source)
        self.assertIn("include_long_notes=include_long_notes", source)
        self.assertIn('"include_long_notes": APP_CONFIG.get(', source)

    def test_localized_control_and_status(self):
        for language in ("en", "es"):
            for key in ("toggle_lns", "ln_on", "ln_off"):
                self.assertNotEqual(i18n.t(key, language), key)


if __name__ == "__main__":
    unittest.main()

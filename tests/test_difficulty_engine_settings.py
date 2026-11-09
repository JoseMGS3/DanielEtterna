"""Engine selector regression tests; safe to run without an Etterna GUI."""
import ast
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import config_manager
import i18n


class DifficultyEngineSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "src" / "daniel_etterna.py").read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.settings = next(node for node in cls.tree.body
                            if isinstance(node, ast.FunctionDef)
                            and node.name == "open_settings")

    def test_legacy_is_default_when_migrating_existing_settings(self):
        defaults = config_manager._merge_defaults({
            "config_version": 8, "nomenclature": "Images",
            "window_sizes": config_manager.DEFAULT_CONFIG["window_sizes"],
        })
        self.assertEqual(defaults["difficulty_engine"], "Legacy")
        self.assertEqual(defaults["nomenclature"], "Images")
        self.assertEqual(defaults["config_version"], 9)

    def test_engine_setting_is_persistent_and_validated(self):
        for name in ("Legacy", "XDC1"):
            with self.subTest(engine=name):
                merged = config_manager._merge_defaults({"difficulty_engine": name})
                self.assertEqual(merged["difficulty_engine"], name)
        for invalid in ("legacy", "xdc1", "", "unrecognized", None, 123):
            with self.subTest(invalid=invalid):
                merged = config_manager._merge_defaults({"difficulty_engine": invalid})
                self.assertEqual(merged["difficulty_engine"], "Legacy")

    def test_settings_roundtrip_preserves_custom_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(config_manager, "get_config_dir",
                              return_value=Path(directory)):
                chosen = config_manager._merge_defaults({
                    "difficulty_engine": "XDC1",
                    "nomenclature": "Images",
                    "language": "es",
                })
                config_manager.save_config(chosen)
                reloaded = config_manager.load_config()
                self.assertEqual(reloaded["difficulty_engine"], "XDC1")
                self.assertEqual(reloaded["nomenclature"], "Images")
                self.assertEqual(reloaded["language"], "es")

    def test_accordion_after_keybinds_and_scrolling(self):
        source = ast.get_source_segment(self.source, self.settings)
        self.assertLess(source.index("restore_button = tk.Button"),
                        source.index("engine_panel = tk.Frame"))
        self.assertLess(source.index("engine_panel = tk.Frame"),
                        source.index("credits_separator = tk.Frame"))
        self.assertIn("engine_body.pack_forget()", source)
        self.assertIn("engine_body.pack(fill=", source)
        self.assertIn("engine_header = tk.Button(", source)
        self.assertIn("general_canvas = tk.Canvas(", source)
        self.assertIn("general_scrollbar = tk.Scrollbar(", source)
        self.assertIn('command=_toggle_engine_section', source)
        self.assertIn('"difficulty_engine": engine_var.get()', source)
        self.assertIn('if engine_var.get() == "XDC1":', source)
        self.assertIn("xdc1_adapter.resolve_xdc1_binary()", source)
        self.assertIn('last_state = None', source)

    def test_runtime_engine_dispatch_uses_real_xdc1_without_replacing_legacy(self):
        source = self.source
        self.assertIn('APP_CONFIG.get("difficulty_engine", "Legacy")', source)
        self.assertIn('if difficulty_engine == "XDC1":', source)
        self.assertIn("chart_loader.normalize_chart_notes(", source)
        self.assertIn("chart_loader.rate_normalized_notes(", source)
        self.assertIn("xdc1_adapter.analyze_notes(", source)
        self.assertIn("algorithm.calculate_notes(", source)
        self.assertIn("def _get_xdc1_default_dan_from_diff(diff):", source)
        self.assertIn("nomenclature_manager.apply_nomenclature(", source)

    def test_both_languages_have_correct_engines(self):
        for lang in ("en", "es"):
            for key in (
                "difficulty_engine", "engine_legacy", "engine_xdc1",
                "engine_legacy_description", "engine_xdc1_description",
                "engine_settings_hint", "engine_missing_message",
                "engine_missing_title", "xdc1_error",
            ):
                with self.subTest(lang=lang, key=key):
                    self.assertNotEqual(i18n.t(key, lang), key)
            self.assertEqual(i18n.t("engine_xdc1", lang), "XDC1")
            self.assertEqual(i18n.t("engine_legacy", lang), "Legacy")

    def test_xdc1_dan_mapper_follows_original_engine_boundaries(self):
        names = next(node for node in self.tree.body
                     if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name)
                             and t.id == "_XDC1_DAN_MEANS" for t in node.targets))
        mapper = next(node for node in self.tree.body
                      if isinstance(node, ast.FunctionDef)
                      and node.name == "_get_xdc1_default_dan_from_diff")
        unit = ast.fix_missing_locations(ast.Module(body=[names, mapper], type_ignores=[]))
        scope = {}
        exec(compile(unit, "<dan mapper test>", "exec"), scope)
        label, numeric = scope["_get_xdc1_default_dan_from_diff"](11.28)
        self.assertEqual((label, numeric), ("Mid-Alpha", 11.5))
        label, numeric = scope["_get_xdc1_default_dan_from_diff"](19.0)
        self.assertEqual((label, numeric), ("Mid-Iota", 19.5))
        label, numeric = scope["_get_xdc1_default_dan_from_diff"](19.60)
        self.assertEqual((label, numeric), ("Mid-Kappa", 20.5))
        label, numeric = scope["_get_xdc1_default_dan_from_diff"](-4.0)
        self.assertEqual(label, "<1st")


if __name__ == "__main__":
    unittest.main()

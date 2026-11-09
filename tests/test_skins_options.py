"""Skins tab regression tests: selection cards instead of dropdowns."""
import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import i18n


class SkinsOptionsTests(unittest.TestCase):
    @staticmethod
    def source():
        return (ROOT / "src" / "daniel_etterna.py").read_text(encoding="utf-8")

    def test_labels_are_localized(self):
        self.assertEqual(i18n.t("skins_tab", "en"), "Skins")
        self.assertEqual(i18n.t("skins_tab", "es"), "Skins")
        self.assertIn("12.08", i18n.t("nomenclature_examples", "es"))

    def test_cards_are_clickable_and_not_comboboxes(self):
        source = self.source()
        tree = ast.parse(source)
        settings = next(
            x for x in tree.body
            if isinstance(x, ast.FunctionDef) and x.name == "open_settings"
        )
        calls = [x for x in ast.walk(settings) if isinstance(x, ast.Call)]
        self.assertTrue(any(
            isinstance(x.func, ast.Attribute)
            and isinstance(x.func.value, ast.Name)
            and x.func.value.id == "tk"
            and x.func.attr == "Radiobutton"
            for x in calls
        ))
        # General retains its language dropdown; Skins must have none.
        self.assertEqual(sum(
            isinstance(x.func, ast.Attribute)
            and isinstance(x.func.value, ast.Name)
            and x.func.value.id == "ttk"
            and x.func.attr == "Combobox"
            for x in calls
        ), 1)
        self.assertIn("cards_scroll = tk.Scrollbar(", source)
        self.assertIn("def _select_nomenclature(value):", source)
        self.assertIn("nomenclature_var.set(value)", source)
        self.assertIn("sample_dp = 12.08", source)
        self.assertIn('"Low-Beta", sample_dp, name', source)

    def test_images_render_and_fall_back_without_changing_dp(self):
        source = self.source()
        self.assertIn('APP_CONFIG.get("nomenclature") == "Images"', source)
        self.assertIn("nomenclature_manager.image_asset_path(dan_numeric)", source)
        self.assertIn("dan_image_renderer.load_dan_image(", source)
        self.assertIn("canvas.create_image(", source)
        self.assertIn("if dan_photo is not None:", source)
        self.assertIn("None if dan_photo is not None else dan_items[-1]", source)
        self.assertIn("if text_item is not None:", source)
        self.assertNotIn("image_status_row =", source)
        self.assertNotIn("images_open_button =", source)
        self.assertNotIn("images_folder_hint =", source)
        self.assertNotIn('tr("images_detected"', source)
        self.assertNotIn('tr("image_assets_hint"', source)
        self.assertIn("    skins_button_bar.grid(\n        row=3, column=0,", source)

    def test_selection_persists_only_on_save(self):
        source = self.source()
        self.assertIn('"nomenclature": nomenclature_var.get(),', source)
        self.assertIn('command=_save_settings,', source)
        self.assertIn('command=_on_close,', source)
        self.assertIn("skins_save_button = tk.Button(", source)
        self.assertIn("skins_cancel_button = tk.Button(", source)


if __name__ == "__main__":
    unittest.main()

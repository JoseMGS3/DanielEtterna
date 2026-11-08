"""Regression tests for the empty Skins options UI in v1.1.1."""
import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import i18n


class SkinsOptionsTests(unittest.TestCase):
    def test_skins_tab_name_is_identical_in_both_languages(self):
        self.assertEqual(i18n.t("skins_tab", "en"), "Skins")
        self.assertEqual(i18n.t("skins_tab", "es"), "Skins")

    def test_selector_labels(self):
        self.assertEqual(i18n.t("nomenclature_label", "en"), "Nomenclature")
        self.assertEqual(i18n.t("nomenclature_label", "es"), "Nomenclatura")
        self.assertEqual(i18n.t("skin_label", "en"), "Skin")
        self.assertEqual(i18n.t("skin_label", "es"), "Skin")

    def test_skins_tab_has_two_empty_readonly_selectors(self):
        source = (ROOT / "src" / "daniel_etterna.py").read_text(encoding="utf-8")
        module = ast.parse(source)
        settings = next(
            node for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name == "open_settings"
        )
        self.assertIn('tab_buttons["skins"]', source)
        self.assertIn('("nomenclature_label", "skin_label")', source)

        empty_dropdowns = []
        for node in ast.walk(settings):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "ttk"
                and func.attr == "Combobox"
            ):
                continue
            keywords = {item.arg: item.value for item in node.keywords}
            values = keywords.get("values")
            state = keywords.get("state")
            if (
                isinstance(values, ast.Tuple) and not values.elts
                and isinstance(state, ast.Constant) and state.value == "readonly"
            ):
                empty_dropdowns.append(node)

        # This combobox is constructed once for each of the two labels.
        self.assertEqual(len(empty_dropdowns), 1)


if __name__ == "__main__":
    unittest.main()

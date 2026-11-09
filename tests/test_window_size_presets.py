"""Checks the percentage presets for all three Etterna layouts.

Only the Tk-independent size definitions are evaluated; starting the GUI
is not required to test pixel dimensions.
"""
import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import i18n

SOURCE = (ROOT / "src" / "daniel_etterna.py").read_text(encoding="utf-8")


def load_size_definitions():
    syntax = ast.parse(SOURCE)
    required_constants = {
        "MODE_COMPACT", "MODE_STATISTICS", "MODE_FULL",
        "COMPACT_HEIGHT", "STATISTICS_HEIGHT", "FULL_HEIGHT",
        "COMPACT_WIDTH", "STATISTICS_WIDTH", "FULL_WIDTH",
        "MODE_HEIGHTS", "MODE_WIDTHS", "WINDOW_SIZE_PRESETS",
    }
    nodes = []
    for node in syntax.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in required_constants
            for target in node.targets
        ):
            nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name == "_scaled_mode_size":
            nodes.append(node)
    namespace = {}
    module = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    exec(compile(module, "<window-size-definitions>", "exec"), namespace)
    return namespace


class WindowSizePresetTests(unittest.TestCase):
    def test_default_dimensions(self):
        ns = load_size_definitions()
        self.assertEqual(
            {
                ns["MODE_FULL"]: (
                    ns["MODE_WIDTHS"][ns["MODE_FULL"]],
                    ns["MODE_HEIGHTS"][ns["MODE_FULL"]],
                ),
                ns["MODE_COMPACT"]: (
                    ns["MODE_WIDTHS"][ns["MODE_COMPACT"]],
                    ns["MODE_HEIGHTS"][ns["MODE_COMPACT"]],
                ),
                ns["MODE_STATISTICS"]: (
                    ns["MODE_WIDTHS"][ns["MODE_STATISTICS"]],
                    ns["MODE_HEIGHTS"][ns["MODE_STATISTICS"]],
                ),
            },
            {
                ns["MODE_FULL"]: (650, 407),
                ns["MODE_COMPACT"]: (550, 72),
                ns["MODE_STATISTICS"]: (650, 116),
            },
        )

    def test_percentage_presets_for_every_layout(self):
        ns = load_size_definitions()
        self.assertEqual(ns["WINDOW_SIZE_PRESETS"], {
            "50%": 0.5, "75%": 0.75, "100%": 1.0,
        })
        sizes = {
            "50%": [(275, 36), (325, 58), (325, 204)],
            "75%": [(413, 54), (488, 87), (488, 305)],
            "100%": [(550, 72), (650, 116), (650, 407)],
        }
        for name, expected in sizes.items():
            for mode, pixels in enumerate(expected):
                with self.subTest(preset=name, mode=mode):
                    self.assertEqual(
                        ns["_scaled_mode_size"](
                            mode, ns["WINDOW_SIZE_PRESETS"][name]
                        ),
                        pixels,
                    )

    def test_buttons_use_percentage_labels_in_both_languages(self):
        for lang in ("en", "es"):
            self.assertEqual(i18n.t("size_50_percent", lang), "50%")
            self.assertEqual(i18n.t("size_75_percent", lang), "75%")
            self.assertEqual(i18n.t("size_100_percent", lang), "100%")
        for preset in ("50%", "75%", "100%"):
            self.assertIn('"' + preset + '",', SOURCE)
        self.assertNotIn('tr("size_small")', SOURCE)
        self.assertNotIn('tr("size_medium")', SOURCE)
        self.assertNotIn('tr("size_large")', SOURCE)

    def test_msd_text_scales_with_statistics_layout(self):
        syntax = ast.parse(SOURCE)
        draw_msd = next(
            node for node in syntax.body
            if isinstance(node, ast.FunctionDef) and node.name == "draw_msd"
        )
        fit_calls = [
            node for node in ast.walk(draw_msd)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_fit_font_to_width"
        ]
        self.assertEqual(len(fit_calls), 2)
        for call in fit_calls:
            self.assertIsInstance(call.args[1], ast.Name)
            self.assertEqual(call.args[1].id, "msd_font")


if __name__ == "__main__":
    unittest.main()

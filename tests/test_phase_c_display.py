"""Phase C regression: distinguish XDC1 graph, verify Dan tiers/badges."""
import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import i18n
import nomenclature_manager
import phase_c_display


class PhaseCDisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "src" / "daniel_etterna.py").read_text(
            encoding="utf-8"
        )
        cls.tree = ast.parse(cls.source)
        names = next(
            node for node in cls.tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == "_XDC1_DAN_MEANS"
                for t in node.targets
            )
        )
        mapper = next(
            node for node in cls.tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_get_xdc1_default_dan_from_diff"
        )
        module = ast.fix_missing_locations(
            ast.Module(body=[names, mapper], type_ignores=[])
        )
        scope = {}
        exec(compile(module, "<xdc1 Dan classification>", "exec"), scope)
        cls.mapper = staticmethod(scope["_get_xdc1_default_dan_from_diff"])
        cls.means = scope["_XDC1_DAN_MEANS"]

    def test_full_graph_captions_identify_engine_source_and_rate(self):
        self.assertEqual(
            phase_c_display.graph_caption("XDC1", 1.25, "en"),
            "XDC1 strain · 1.25x",
        )
        self.assertEqual(
            phase_c_display.graph_caption("XDC1", 1.25, "es"),
            "Esfuerzo XDC1 · 1.25x",
        )
        self.assertEqual(
            phase_c_display.graph_caption("Legacy", 0.75, "en"),
            "Legacy strain · 0.75x",
        )
        self.assertEqual(
            phase_c_display.graph_caption("Legacy", 1, "es"),
            "Esfuerzo Legacy · 1x",
        )
        for bad in (None, 0, -1, float("inf"), float("nan"), "broken"):
            with self.subTest(bad=bad):
                self.assertTrue(
                    phase_c_display.graph_caption("XDC1", bad).endswith("1x")
                )

    def test_graph_has_no_engine_caption_and_skillsets_have_no_engine_prefix(self):
        updater = next(
            node for node in self.tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "update_dan_text"
        )
        code = ast.get_source_segment(self.source, updater)
        self.assertNotIn("phase_c_display.graph_caption(", code)
        self.assertNotIn('tags="engine_graph_caption"', self.source)
        self.assertIn('f"{skillset_str}  {_last_sr:.2f} Dan · "', self.source)
        self.assertNotIn('f"XDC1 · {skillset_str}', self.source)
        self.assertIn("graph.set_data(times, strain)", self.source)

    def test_xdc1_dan_means_map_exactly_to_centered_tiers(self):
        for i, (name, mean) in enumerate(self.means.items()):
            with self.subTest(dan=name, value=mean):
                label, numeric = self.mapper(mean)
                self.assertEqual(label, "Mid-" + name)
                self.assertEqual(numeric, 4 + i + .5)

    def test_tier_boundaries_are_contiguous_not_off_by_one(self):
        names = list(self.means)
        values = list(self.means.values())
        for i in range(len(values) - 1):
            midpoint = (values[i] + values[i + 1]) / 2
            with self.subTest(before=names[i], after=names[i + 1]):
                below_label, _ = self.mapper(midpoint - .000001)
                at_label, numeric = self.mapper(midpoint)
                self.assertEqual(below_label, "High-" + names[i])
                self.assertEqual(at_label, "Low-" + names[i + 1])
                self.assertEqual(numeric, 5 + i)
        high = values[-1] + (values[-1] - values[-2]) / 2
        self.assertEqual(self.mapper(high), ("? ? ? ? ?", "N/A"))
        self.assertEqual(self.mapper(float("nan")), ("? ? ? ? ?", "N/A"))

    def test_xdc1_classification_preserves_five_nomenclatures(self):
        cases = ("Default", "MMA", "--/++", "Mania tracker", "Images")
        for raw in (11.28, 12.04, 16.98, 19.60):
            default_label, numeric = self.mapper(raw)
            for skin in cases:
                with self.subTest(raw=raw, nomenclature=skin):
                    label, dp = nomenclature_manager.apply_nomenclature(
                        default_label, numeric, skin,
                    )
                    self.assertTrue(label and isinstance(label, str))
                    self.assertEqual(dp, numeric)
        _, alpha_numeric = self.mapper(self.means["Alpha"])
        _, beta_numeric = self.mapper(self.means["Beta"])
        _, kappa_numeric = self.mapper(self.means["Kappa"])
        self.assertEqual(
            nomenclature_manager.image_asset_filename(alpha_numeric),
            "alpha.webp",
        )
        self.assertEqual(
            nomenclature_manager.image_asset_filename(beta_numeric),
            "beta.webp",
        )
        self.assertEqual(
            nomenclature_manager.image_asset_filename(kappa_numeric),
            "kappa.webp",
        )

    def test_both_languages_define_graph_caption_strings(self):
        for lang in ("en", "es"):
            for key in ("graph_xdc1_strain", "graph_legacy_strain"):
                self.assertNotEqual(i18n.t(key, lang), key)


if __name__ == "__main__":
    unittest.main()

"""Regression tests for Default, MMA, --/++, and Mania tracker nomenclatures."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import config_manager
import nomenclature_manager as names


class NomenclatureTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.folder = Path(self.tempdir.name)
        patcher = patch.object(config_manager, "get_config_dir", return_value=self.folder)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_installs_two_editable_json_files(self):
        self.assertEqual(names.available_names()[:2], ["Default", "MMA"])
        self.assertTrue((self.folder / "nomenclatures" / "Default.json").is_file())
        self.assertTrue((self.folder / "nomenclatures" / "MMA.json").is_file())

    def test_signs_profile_is_installed_and_listed_by_display_name(self):
        self.assertEqual(names.available_names()[:3], ["Default", "MMA", "--/++"])
        saved = self.folder / "nomenclatures" / "PlusMinus.json"
        self.assertTrue(saved.is_file())
        self.assertEqual(names.load_profile("--/++")["name"], "--/++")
        # A slash in the label must not create a nested directory.
        self.assertFalse((self.folder / "nomenclatures" / "--").exists())

    def test_signs_five_tiers_without_numeric_shift(self):
        examples = [
            (9.0, ("9--", 9.0)),
            (9.1, ("9--", 9.1)),
            (9.2, ("9-", 9.2)),
            (9.3, ("9-", 9.3)),
            (9.4, ("9", 9.4)),
            (9.5, ("9", 9.5)),
            (9.6, ("9+", 9.6)),
            (9.7, ("9+", 9.7)),
            (9.8, ("9++", 9.8)),
            (9.9, ("9++", 9.9)),
            (10.0, ("10--", 10.0)),
            (11.1, ("Alpha--", 11.1)),
            (11.5, ("Alpha", 11.5)),
            (11.8, ("Alpha++", 11.8)),
            (16.8, ("Emik Zeta++", 16.8)),
            (17.5, ("Thaumiel Eta", 17.5)),
            (18.6, ("CloverWisp Theta+", 18.6)),
        ]
        for value, expected in examples:
            with self.subTest(value=value):
                self.assertEqual(
                    names.apply_nomenclature("Low-9th", value, "--/++"),
                    expected,
                )

    def test_signs_does_not_invent_unsupported_dans(self):
        self.assertEqual(
            names.apply_nomenclature("<1st", 0.0, "--/++"),
            ("<1st", 0.0),
        )
        self.assertEqual(
            names.apply_nomenclature("? ? ? ? ?", "N/A", "--/++"),
            ("? ? ? ? ?", "N/A"),
        )

    def test_signs_files_preserve_user_edits(self):
        names.ensure_builtin_files()
        path = self.folder / "nomenclatures" / "PlusMinus.json"
        source = path.read_text(encoding="utf-8")
        updated = source.replace('"Alpha"', '"Custom Alpha"')
        path.write_text(updated, encoding="utf-8")
        names.ensure_builtin_files()
        self.assertEqual(path.read_text(encoding="utf-8"), updated)
        self.assertEqual(
            names.apply_nomenclature("Mid-Alpha", 11.8, "--/++"),
            ("Custom Alpha++", 11.8),
        )

    def test_mania_tracker_is_installed_and_selectable(self):
        self.assertEqual(
            names.available_names()[:4],
            ["Default", "MMA", "--/++", "Mania tracker"],
        )
        profile_file = self.folder / "nomenclatures" / "Mania tracker.json"
        self.assertTrue(profile_file.is_file())
        profile = names.load_profile("Mania tracker")
        mma = names.load_profile("MMA")
        self.assertEqual(profile["name"], "Mania tracker")
        self.assertEqual(profile["numeric_offset"], 0)
        self.assertEqual(profile["label_mode"], mma["label_mode"])
        self.assertEqual(profile["tiers"], mma["tiers"])
        self.assertEqual(profile["dans"], mma["dans"])

    def test_mania_tracker_matches_mma_names_without_shift(self):
        examples = [
            (9.0, ("Reform 9 mid", 9.0)),
            (9.3, ("Reform 9 high", 9.3)),
            (9.5, ("Reform 10 low", 9.5)),
            (10.5, ("Alpha low", 10.5)),
            (10.7, ("Alpha mid/low", 10.7)),
            (10.9, ("Alpha mid", 10.9)),
            (11.0, ("Alpha mid", 11.0)),
            (11.1, ("Alpha mid/high", 11.1)),
            (11.3, ("Alpha high", 11.3)),
            (11.5, ("Beta low", 11.5)),
            (12.0, ("Beta mid", 12.0)),
            (16.0, ("Emik Zeta mid", 16.0)),
            (17.0, ("Thaumiel Eta mid", 17.0)),
            (18.0, ("CloverWisp Theta mid", 18.0)),
        ]
        for numeric, expected in examples:
            with self.subTest(numeric=numeric):
                self.assertEqual(
                    names.apply_nomenclature("Mid-Alpha", numeric, "Mania tracker"),
                    expected,
                )

    def test_mania_tracker_selection_is_persistent(self):
        with patch.object(config_manager, "get_config_path",
                          return_value=self.folder / "config.json"):
            cfg = config_manager._merge_defaults({"nomenclature": "Mania tracker"})
            config_manager.save_config(cfg)
            self.assertEqual(
                config_manager.load_config()["nomenclature"], "Mania tracker"
            )

    def test_mania_tracker_does_not_change_unsupported_ranges(self):
        self.assertEqual(
            names.apply_nomenclature("<1st", 0.0, "Mania tracker"),
            ("<1st", 0.0),
        )
        self.assertEqual(
            names.apply_nomenclature("? ? ? ? ?", "N/A", "Mania tracker"),
            ("? ? ? ? ?", "N/A"),
        )

    def test_default_never_changes_legacy_labels_or_numbers(self):
        for label, numeric in [
            ("Low-Alpha", 11.0),
            ("Mid-Alpha", 11.5),
            ("High-Alpha", 11.99),
            ("Low-1st", 1.01),
            ("<1st", 0.0),
            ("? ? ? ? ?", "N/A"),
        ]:
            self.assertEqual(names.apply_nomenclature(label, numeric, "Default"),
                             (label, numeric))

    def test_mma_is_shifted_by_half_dan(self):
        examples = [
            (11.0, ("Alpha low", 10.5)),
            (11.2, ("Alpha mid/low", 10.7)),
            (11.4, ("Alpha mid", 10.9)),
            (11.5, ("Alpha mid", 11.0)),
            (11.6, ("Alpha mid/high", 11.1)),
            (11.8, ("Alpha high", 11.3)),
            (12.0, ("Beta low", 11.5)),
            (12.5, ("Beta mid", 12.0)),
            (17.5, ("Thaumiel Eta mid", 17.0)),
            (18.5, ("CloverWisp Theta mid", 18.0)),
        ]
        for default_numeric, expected in examples:
            with self.subTest(default_numeric=default_numeric):
                actual = names.apply_nomenclature("Mid-Alpha", default_numeric, "MMA")
                self.assertEqual(actual, expected)

    def test_mma_does_not_fabricate_out_of_range_ratings(self):
        self.assertEqual(
            names.apply_nomenclature("? ? ? ? ?", "N/A", "MMA"),
            ("? ? ? ? ?", "N/A"),
        )
        self.assertEqual(
            names.apply_nomenclature("<1st", 0.0, "MMA"),
            ("<1st", 0.0),
        )

    def test_profiles_survive_reinitialization_and_user_edits(self):
        names.ensure_builtin_files()
        mma_file = self.folder / "nomenclatures" / "MMA.json"
        original = mma_file.read_text(encoding="utf-8")
        edited = original.replace('"Emik Zeta"', '"Custom Zeta"')
        mma_file.write_text(edited, encoding="utf-8")
        names.ensure_builtin_files()
        self.assertEqual(mma_file.read_text(encoding="utf-8"), edited)
        self.assertEqual(
            names.apply_nomenclature("Mid-Zeta", 16.5, "MMA"),
            ("Custom Zeta mid", 16.0),
        )

    def test_corrupt_file_falls_back_without_crashing(self):
        names.ensure_builtin_files()
        (self.folder / "nomenclatures" / "MMA.json").write_text("{", encoding="utf-8")
        self.assertEqual(
            names.apply_nomenclature("Low-Alpha", 11.0, "MMA"),
            ("Alpha low", 10.5),
        )

    def test_config_roundtrip_preserves_selected_nomenclature(self):
        with patch.object(config_manager, "get_config_path",
                          return_value=self.folder / "config.json"):
            for selected in ("MMA", "--/++"):
                cfg = config_manager._merge_defaults({"nomenclature": selected})
                self.assertEqual(cfg["nomenclature"], selected)
                config_manager.save_config(cfg)
                self.assertEqual(config_manager.load_config()["nomenclature"], selected)

    def test_color_keys_for_both_formats(self):
        self.assertEqual(names.color_key_from_label("Low-Alpha"), "Alpha")
        self.assertEqual(names.color_key_from_label("Alpha low"), "Alpha")
        self.assertEqual(names.color_key_from_label("Emik Zeta high"), "Zeta")
        self.assertEqual(names.color_key_from_label("Thaumiel Eta mid"), "Eta")
        self.assertEqual(names.color_key_from_label("CloverWisp Theta mid"), "Theta")
        self.assertEqual(names.color_key_from_label("Alpha++"), "Alpha")
        self.assertEqual(names.color_key_from_label("Emik Zeta++"), "Zeta")
        self.assertEqual(names.color_key_from_label("Thaumiel Eta--"), "Eta")


if __name__ == "__main__":
    unittest.main()

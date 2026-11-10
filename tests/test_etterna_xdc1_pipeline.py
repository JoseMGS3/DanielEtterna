"""Etterna -> XDC1 pipeline, bridge clock and skillsets regression tests."""
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import chart_loader
import etterna_xdc1_pipeline as pipeline


class EtternaPipelineTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)

    def write(self, name, body):
        path = self.folder / name
        path.write_text(body, encoding="utf-8")
        return chart_loader.load_chart_file(path)

    def test_preview_and_gameplay_clocks_follow_rate_adjusted_notes(self):
        self.assertEqual(pipeline.chart_position_ms(5000, 1.25), 4000)
        self.assertEqual(pipeline.chart_position_ms(5000, 1.25, 0.1), 4100)
        self.assertEqual(pipeline.chart_position_ms(5000, 0.75, 0.1),
                         5000 / .75 + 100)
        self.assertEqual(pipeline.chart_position_ms(-500, 1.5), -500 / 1.5)
        self.assertEqual(pipeline.chart_position_ms(1000, 1, -1), 1000)

    def test_bridge_rate_and_stepstype_safety(self):
        for raw in ("1.5", 0.75, 1):
            self.assertEqual(pipeline.normalize_bridge_rate(raw), float(raw))
        for raw in ("", None, "NaN", "inf", 0, -2, "broken"):
            with self.subTest(raw=raw):
                self.assertEqual(pipeline.normalize_bridge_rate(raw), 1.0)
        for value in ("StepsType_Dance_Single", "dance-single",
                      "dance_single", ""):
            self.assertTrue(pipeline.is_4k_stepstype(value))
        for value in ("StepsType_Dance_Double", "dance-double",
                      "StepsType_Pump_Single", "dance-solo"):
            self.assertFalse(pipeline.is_4k_stepstype(value))

    def test_invalid_bridge_clocks_are_rejected(self):
        cases = [(100, 0, 0), (100, float("nan"), 0),
                 (float("inf"), 1, 0), (10, 1, float("nan"))]
        for music, rate, elapsed in cases:
            with self.subTest(case=(music, rate, elapsed)):
                with self.assertRaises(ValueError):
                    pipeline.chart_position_ms(music, rate, elapsed)

    def test_xdc1_skillsets_use_original_relevance_rules(self):
        items = {
            "stream": 74, "jumpstream": 91,
            "handstream": 81, "speedjack": 44, "chordjack": 22,
            "technical": 88, "release": 13,
        }
        self.assertEqual(
            pipeline.relevant_xdc1_skillsets(100, items),
            [("jumpstream", 91), ("technical", 88), ("handstream", 81)],
        )
        very_low = dict.fromkeys(items, 1.0)
        very_low["release"] = 15.0
        self.assertEqual(
            pipeline.relevant_xdc1_skillsets(100, very_low),
            [("release", 15.0)],
        )

    def test_ssc_ambiguous_chart_requires_exact_bridge_description(self):
        data = self.write(
            "duplicates.ssc",
            "#BPMS:0=120;\n"
            "#NOTEDATA:;\n#STEPSTYPE:dance-single;\n"
            "#DIFFICULTY:Challenge;\n#METER:17;\n"
            "#DESCRIPTION:Original;\n"
            "#NOTES:1000\n0000\n0000\n0000;\n"
            "#NOTEDATA:;\n#STEPSTYPE:dance-single;\n"
            "#DIFFICULTY:Challenge;\n#METER:17;\n"
            "#DESCRIPTION:Extended;\n#BPMS:0=240;\n"
            "#NOTES:0100\n0000\n0000\n0000;\n",
        )
        first, second = data["charts"]
        self.assertIs(
            pipeline.select_stepmania_chart(
                data, "Difficulty_Challenge", "17", "Extended",
                "StepsType_Dance_Single",
            ), second,
        )
        self.assertIs(
            pipeline.select_stepmania_chart(
                data, "Difficulty_Challenge", "17", "Original",
                "StepsType_Dance_Single",
            ), first,
        )
        self.assertIsNone(
            pipeline.select_stepmania_chart(
                data, "Difficulty_Challenge", "17", "",
                "StepsType_Dance_Single",
            )
        )
        self.assertIsNone(
            pipeline.select_stepmania_chart(
                data, "Difficulty_Challenge", "17", "Extended",
                "StepsType_Dance_Double",
            )
        )

    def test_pipeline_uses_selected_ssc_timing_and_long_note_rate(self):
        data = self.write(
            "selected.ssc",
            "#BPMS:0=120;\n#NOTEDATA:;\n"
            "#STEPSTYPE:dance-single;\n"
            "#DIFFICULTY:Hard;\n#METER:10;\n"
            "#NOTES:\n2000\n0000\n3000\n0100;\n"
            "#NOTEDATA:;\n"
            "#STEPSTYPE:dance-single;\n"
            "#DIFFICULTY:Challenge;\n#METER:18;\n"
            "#BPMS:0=240;\n"
            "#NOTES:\n4000\n0100\n3000\n0000;\n",
        )
        called = []
        result_data = {
            "grid": [0.0, 100.0, 200.0, 300.0, 400.0],
            "strain_rested": [0.0, 2.0, 3.0, 1.0, 0.0],
            "rating": 12.5,
            "rating_rice": 12.0,
            "rating_raw": 100.0,
            "skillsets_raw": {
                "stream": 90.0, "jumpstream": 87.0,
                "handstream": 85.0, "speedjack": 40.0,
                "chordjack": 35.0, "technical": 70.0,
                "release": 65.0,
            },
        }
        def capture(notes, executable=None):
            called.append(notes)
            return result_data
        with patch.object(pipeline.xdc1_adapter, "analyze_notes",
                          side_effect=capture):
            result = pipeline.analyze_etterna_chart(
                data, data["charts"][1], rate=1.25,
            )
        self.assertEqual(called, [
            [(0, 0, 400), (1, 200, -1)]
        ])
        self.assertEqual(result["rating"], 12.5)
        self.assertEqual(
            [name for name, _ in result["top_skillsets"]],
            ["stream", "jumpstream", "handstream"],
        )
        self.assertEqual(result["skillsets_raw"]["overall"], 100.0)
        self.assertEqual(len(result["times"]), 5)
        self.assertTrue(all(math.isfinite(x) for x in result["strain"]))

    def test_pipeline_can_disable_ln_without_changing_source_chart(self):
        data = self.write(
            "selected.sm",
            "#BPMS:0=120;\n"
            "#NOTES:dance-single::Hard:10:0,0,0,0,0:\n"
            "2000\n0100\n3000\n0000;\n",
        )
        def simple_result(notes, executable=None):
            self.assertEqual(notes, [(0, 0, -1), (1, 500, -1)])
            return {
                "grid": [0.0, 500.0, 1000.0],
                "strain_rested": [0.0, 1.0, 0.0],
                "rating": 9.0, "rating_rice": 9.0,
                "rating_raw": 80.0,
                "skillsets_raw": dict.fromkeys(pipeline.XDC1_SKILLSETS, 60.0),
            }
        with patch.object(pipeline.xdc1_adapter, "analyze_notes",
                          side_effect=simple_result):
            result = pipeline.analyze_etterna_chart(
                data, data["charts"][0], include_long_notes=False,
            )
        self.assertEqual(result["rating"], 9.0)
        self.assertEqual(
            chart_loader.normalize_chart_notes(data, data["charts"][0]),
            [(0, 0, 1000), (1, 500, -1)],
        )

    def test_wasd_swaps_only_columns_two_and_three(self):
        notes = [
            (0, 0, -1), (1, 250, 900), (2, 250, -1),
            (3, 600, 1100),
        ]
        original = list(notes)
        self.assertEqual(pipeline.remap_xdc1_columns(notes), original)
        self.assertEqual(
            pipeline.remap_xdc1_columns(notes, "wasd"),
            [(0, 0, -1), (1, 250, -1), (2, 250, 900),
             (3, 600, 1100)],
        )
        self.assertEqual(notes, original)
        self.assertEqual(
            pipeline.remap_xdc1_columns(
                pipeline.remap_xdc1_columns(notes, "wasd"), "wasd",
            ),
            original,
        )
        with self.assertRaisesRegex(ValueError, "Unknown XDC1 column layout"):
            pipeline.remap_xdc1_columns(notes, "invalid")

    def test_wasd_profile_is_applied_after_rate_and_ln_conversion(self):
        data = self.write(
            "wasd.sm",
            "#BPMS:0=120;\n"
            "#NOTES:dance-single::Hard:10:0,0,0,0,0:\n"
            "0200\n0001\n0300\n0010;\n",
        )
        cases = [
            ("standard", True, [(1, 0, 1000), (3, 500, -1),
                                (2, 1500, -1)]),
            ("wasd", True, [(2, 0, 1000), (3, 500, -1),
                            (1, 1500, -1)]),
            ("wasd", False, [(2, 0, -1), (3, 500, -1),
                             (1, 1500, -1)]),
        ]
        # The engine sees only a remapping; all chart timing, LN duration and
        # 4K note heads must otherwise remain unchanged.
        for layout, ln, expected in cases:
            with self.subTest(layout=layout, include_long_notes=ln):
                with patch.object(pipeline.xdc1_adapter, "analyze_notes") as analyze:
                    analyze.return_value = {
                        "grid": [0.0, 500.0, 1000.0, 1500.0, 2000.0],
                        "strain_rested": [0.0, 1.0, 1.0, 1.0, 0.0],
                        "rating": 12.0, "rating_rice": 11.0,
                        "rating_raw": 80.0,
                        "skillsets_raw": dict.fromkeys(
                            pipeline.XDC1_SKILLSETS, 70.0,
                        ),
                    }
                    pipeline.analyze_etterna_chart(
                        data, data["charts"][0], rate=1.0,
                        include_long_notes=ln, column_layout=layout,
                    )
                    self.assertEqual(analyze.call_args.args[0], expected)

    def test_native_wasd_matches_manual_swap_for_real_engine(self):
        import xdc1_adapter

        measures = ["1200\n0010\n0300\n0100"] + [
            "1010\n0100\n1000\n0001"
        ] * 10
        data = self.write(
            "wasd_native.sm",
            "#BPMS:0=150;\n"
            "#NOTES:dance-single::Challenge:18:0,0,0,0,0:\n"
            + ",\n".join(measures) + ";\n",
        )
        normalized = chart_loader.normalize_chart_notes(data, data["charts"][0])
        rated = chart_loader.rate_normalized_notes(normalized, rate=1.2)
        remapped = pipeline.remap_xdc1_columns(rated, "wasd")
        baseline = xdc1_adapter.analyze_notes(remapped)
        result = pipeline.analyze_etterna_chart(
            data, data["charts"][0], rate=1.2, column_layout="wasd",
        )
        self.assertAlmostEqual(result["rating"], baseline["rating"])
        self.assertAlmostEqual(result["rating_rice"], baseline["rating_rice"])
        self.assertEqual(result["skillsets_raw"]["overall"], baseline["rating_raw"])

    def test_native_engine_accepts_real_selected_ssc_with_hold_and_rate(self):
        import xdc1_adapter

        measures = [
            "2000\n0100\n0010\n0001",  # a hold starts at beat zero
            "0000\n0100\n3000\n0001",  # tail at beat six
        ]
        measures += ["1000\n0100\n0010\n0001"] * 10
        data = self.write(
            "live.ssc",
            "#BPMS:0=180;\n#STOPS:8=0.1;\n"
            "#NOTEDATA:;\n#STEPSTYPE:dance-single;\n"
            "#DIFFICULTY:Challenge;\n#METER:18;\n"
            "#DESCRIPTION:Etterna fixture;\n"
            "#NOTES:\n" + ",\n".join(measures) + ";\n",
        )
        selected = pipeline.select_stepmania_chart(
            data, "Difficulty_Challenge", "18", "Etterna fixture",
            "StepsType_Dance_Single",
        )
        self.assertIs(selected, data["charts"][0])
        result = pipeline.analyze_etterna_chart(
            data, selected, rate=1.3,
        )
        normalized = chart_loader.normalize_chart_notes(data, selected)
        self.assertTrue(any(tail != -1 for _, _, tail in normalized))
        rated = chart_loader.rate_normalized_notes(normalized, rate=1.3)
        baseline = xdc1_adapter.analyze_notes(rated)
        self.assertAlmostEqual(result["rating"], baseline["rating"])
        self.assertEqual(result["rating_rice"], baseline["rating_rice"])
        self.assertEqual(set(result["skillsets_raw"]),
                         {"overall", *pipeline.XDC1_SKILLSETS})
        self.assertGreater(len(result["times"]), 2)
        self.assertEqual(len(result["times"]), len(result["strain"]))
        self.assertTrue(all(math.isfinite(v) for v in result["strain"]))

    def test_selected_chart_must_be_supplied_and_warps_are_rejected(self):
        data = self.write(
            "warped.sm",
            "#BPMS:0=120;\n#WARPS:1=4;\n"
            "#NOTES:dance-single::Hard:10:0,0,0,0,0:\n"
            "1000\n0100\n0000\n0000;\n",
        )
        with self.assertRaisesRegex(ValueError, "Select"):
            pipeline.analyze_etterna_chart(data)
        with self.assertRaises(NotImplementedError):
            pipeline.analyze_etterna_chart(data, data["charts"][0])


if __name__ == "__main__":
    unittest.main()

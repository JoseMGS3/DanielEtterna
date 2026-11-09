"""2.0 note-normalization regression tests (no C++ engine required)."""
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import chart_loader as loader


class NormalizedChartTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)

    def write(self, name, content):
        target = self.folder / name
        target.write_text(content, encoding="utf-8")
        return loader.load_chart_file(target)

    def sm(self, rows, timing=""):
        bpm = "" if "#BPMS:" in timing else "#BPMS:0=120;\n"
        return self.write(
            "sample.sm",
            "#TITLE:Example;\n" + bpm + timing
            + "\n#NOTES:dance-single::Hard:10:0,0,0,0,0:\n"
            + rows + "\n;\n",
        )

    def test_osu_preserves_legacy_pairs_and_exposes_hold_ends(self):
        data = self.write(
            "notes.osu",
            "osu file format v14\n"
            "CircleSize:4\n[HitObjects]\n"
            "64,192,1000,1,0,0:0:0:0:\n"
            "192,192,1500,128,0,2100:0:0:0:\n",
        )
        self.assertEqual(data["notes"], [(0, 1000), (1, 1500)])
        self.assertEqual(
            loader.normalize_chart_notes(data),
            [(0, 1000, -1), (1, 1500, 2100)],
        )

    def test_osu_rejects_non_four_key_charts(self):
        data = self.write(
            "six.osu",
            "CircleSize:6\n[HitObjects]\n64,192,1000,1,0,0:0:0:0:\n",
        )
        with self.assertRaisesRegex(ValueError, "4K"):
            loader.normalize_chart_notes(data)

    def test_sm_hold_spans_measures_and_legacy_output_is_preserved(self):
        data = self.sm(
            "2000\n0100\n000M\n0000,\n"
            "0000\n3000\n0000\n0000"
        )
        chart = data["charts"][0]
        self.assertEqual(
            loader.normalize_chart_notes(data, chart),
            [(0, 0, 2500), (1, 500, -1)],
        )
        old, ignored = loader.convert_stepmania_chart(data, chart)
        self.assertEqual(old, [(0, 0.0), (1, 500.0)])
        self.assertEqual(ignored["M"], 1)

    def test_sm_roll_end_and_skipped_mines_lifts_fakes(self):
        data = self.sm("4000\n000L\n000F\n3000")
        self.assertEqual(
            loader.normalize_chart_notes(data, data["charts"][0]),
            [(0, 0, 1500)],
        )

    def test_sm_uses_bpm_changes_stops_delays_and_offset(self):
        data = self.sm(
            "2000\n0100\n3000\n0000",
            timing=(
                "#BPMS:0=120,1=240;\n"
                "#STOPS:1=0.3;\n"
                "#DELAYS:1=0.2;\n"
                "#OFFSET:0.1;\n"
            ),
        )
        self.assertEqual(
            loader.normalize_chart_notes(data, data["charts"][0]),
            [(0, -100, 1150), (1, 600, -1)],
        )

    def test_ssc_chart_specific_timing_and_empty_stop_override(self):
        data = self.write(
            "override.ssc",
            "#BPMS:0=120;\n#STOPS:1=2;\n#OFFSET:0;\n"
            "#NOTEDATA:;\n#STEPSTYPE:dance-single;\n"
            "#DIFFICULTY:Hard;\n#METER:10;\n"
            "#BPMS:0=240;\n#STOPS:;\n#OFFSET:0.1;\n"
            "#NOTES:\n2000\n0000\n3000\n0000;\n"
            "#NOTEDATA:;\n#STEPSTYPE:dance-single;\n"
            "#DIFFICULTY:Easy;\n#METER:4;\n"
            "#NOTES:\n1000\n0000\n0100\n0000;\n",
        )
        first, second = data["charts"]
        self.assertEqual(
            loader.normalize_chart_notes(data, first),
            [(0, -100, 400)],
        )
        self.assertEqual(
            loader.normalize_chart_notes(data, second),
            [(0, 0, -1), (1, 3000, -1)],
        )
        # Converting an SSC chart must never mix notes from other charts.
        self.assertEqual(len(loader.normalize_chart_notes(data, first)), 1)

    def test_chart_must_be_selected_for_stepmania(self):
        data = self.sm("1000\n0000\n0000\n0000")
        with self.assertRaisesRegex(ValueError, "Select"):
            loader.normalize_chart_notes(data)

    def test_sm_warps_are_rejected_without_approximation(self):
        data = self.sm("1000\n0000\n0000\n0000",
                       timing="#WARPS:1=2;\n")
        with self.assertRaisesRegex(NotImplementedError, "WARPS"):
            loader.normalize_chart_notes(data, data["charts"][0])

    def test_ssc_warps_use_chart_override(self):
        data = self.write(
            "warps.ssc",
            "#BPMS:0=120;\n#WARPS:1=2;\n#NOTEDATA:;\n"
            "#STEPSTYPE:dance-single;\n#DIFFICULTY:Hard;\n"
            "#METER:10;\n#WARPS:;\n"
            "#NOTES:\n1000\n0000\n0000\n0000;\n",
        )
        self.assertEqual(
            loader.normalize_chart_notes(data, data["charts"][0]),
            [(0, 0, -1)],
        )

    def test_malformed_holds_are_reported(self):
        cases = {
            "orphan tail": "3000\n0000\n0000\n0000",
            "unclosed hold": "2000\n0000\n0000\n0000",
            "overlapping holds": "2000\n2000\n3000\n0000",
            "tap on hold": "2000\n1000\n3000\n0000",
            "non-four-key": "10000\n00000\n00000\n00000",
            "unsupported symbol": "A000\n0000\n0000\n0000",
        }
        for name, rows in cases.items():
            with self.subTest(case=name):
                data = self.sm(rows)
                with self.assertRaises(ValueError):
                    loader.normalize_chart_notes(data, data["charts"][0])

    def test_rate_scaling_preserves_tails_and_can_disable_ln(self):
        notes = [(0, -100, 1150), (1, 600, -1)]
        self.assertEqual(
            loader.rate_normalized_notes(notes, rate=1.5),
            [(0, -67, 766), (1, 400, -1)],
        )
        self.assertEqual(
            loader.rate_normalized_notes(notes, rate=1.5,
                                         include_long_notes=False),
            [(0, -67, -1), (1, 400, -1)],
        )
        self.assertEqual(
            loader.rate_normalized_notes([(0, 100, 400)], rate=0.75),
            [(0, 133, 533)],
        )

    def test_hold_end_must_not_be_confused_with_tap_sentinel(self):
        data = self.sm(
            "2000\n0000\n3000\n0000",
            timing="#OFFSET:1.001;\n",
        )
        with self.assertRaisesRegex(ValueError, "reserved tap marker"):
            loader.normalize_chart_notes(data, data["charts"][0])

        with self.assertRaisesRegex(ValueError, "after rate scaling"):
            loader.rate_normalized_notes(
                [(0, -3, -2)], rate=2.0
            )

    def test_invalid_rates_rejected(self):
        for rate in (0.0, -1.0, float("nan"), float("inf")):
            with self.subTest(rate=rate):
                with self.assertRaises(ValueError):
                    loader.rate_normalized_notes([], rate=rate)


if __name__ == "__main__":
    unittest.main()

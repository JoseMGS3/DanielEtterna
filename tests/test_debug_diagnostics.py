"""Opt-in debug console regression tests, independent of Etterna/Tk."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import chart_loader
import debug_diagnostics as debug


class DebugDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)

    def write(self, name, content):
        path = self.folder / name
        path.write_text(content, encoding="utf-8")
        return chart_loader.load_chart_file(path)

    def test_counts_sm_taps_holds_rolls_and_not_hold_tails(self):
        data = self.write(
            "notes.sm",
            "#BPMS:0=120;\n#NOTES:dance-single::Hard:11:0,0,0,0,0:\n"
            "2000\n0100\n0040\n3000,\n"
            "0000\n0030\n0001\n0000;\n"
        )
        counts = debug.count_chart_notes(data, data["charts"][0])
        self.assertEqual(counts, {
            "taps": 2, "holds": 1, "rolls": 1, "total": 4,
        })
        notes = chart_loader.normalize_chart_notes(data, data["charts"][0])
        self.assertEqual(len(notes), counts["total"])

    def test_counts_only_selected_ssc_and_osu_holds(self):
        data = self.write(
            "two.ssc",
            "#BPMS:0=120;\n"
            "#NOTEDATA:;\n#STEPSTYPE:dance-single;\n"
            "#DIFFICULTY:Hard;\n#METER:9;\n"
            "#NOTES:\n1000\n0100\n0000\n0000;\n"
            "#NOTEDATA:;\n#STEPSTYPE:dance-single;\n"
            "#DIFFICULTY:Challenge;\n#METER:15;\n"
            "#NOTES:\n2000\n0040\n3000\n0030;\n",
        )
        self.assertEqual(
            debug.count_chart_notes(data, data["charts"][0])["taps"], 2,
        )
        self.assertEqual(
            debug.count_chart_notes(data, data["charts"][1]),
            {"taps": 0, "holds": 1, "rolls": 1, "total": 2},
        )
        with self.assertRaisesRegex(ValueError, "Selected"):
            debug.count_chart_notes(data)
        osu = self.write(
            "notes.osu",
            "osu file format v14\nCircleSize:4\n[HitObjects]\n"
            "64,192,1000,1,0,0:0:0:0:\n"
            "192,192,1500,128,0,2100:0:0:0:\n",
        )
        self.assertEqual(
            debug.count_chart_notes(osu),
            {"taps": 1, "holds": 1, "rolls": 0, "total": 2},
        )

    def test_bridge_source_rate_and_sample_age_without_false_sync_claim(self):
        state = debug.bridge_health(
            connection="ready", chart_rate=1.25, now=10,
            menu_time=5000, menu_rate=1.25, menu_received=9.9,
            graph_start=0, graph_end=70000,
        )
        self.assertEqual(state["source"], "Menu/Preview")
        self.assertAlmostEqual(state["cursor_ms"], 4100.0)
        self.assertIn("NOT verified", state["clock_status"])

        gameplay = debug.bridge_health(
            connection="ready", chart_rate=1.25, now=10,
            menu_time=5000, menu_rate=1.25, menu_received=9.9,
            gameplay_time=8000, gameplay_rate=1.5,
            gameplay_received=9.98, gameplay_active=True,
        )
        self.assertEqual(gameplay["source"], "Gameplay")
        self.assertIn("RATE MISMATCH", gameplay["clock_status"])

        stale = debug.bridge_health(
            connection="ready", chart_rate=1.25, now=10,
            menu_received=8.0,
        )
        self.assertEqual(stale["source"], "No fresh sample")
        self.assertIn("Waiting", stale["clock_status"])

    def test_debug_starts_a_new_local_log_and_reports_calculation(self):
        with patch.object(debug, "enabled", True):
            with patch.object(debug, "_log_path", None):
                debug.configure(self.folder)
                debug.report_calculation(
                    engine="XDC1", path="example.ssc", difficulty="Challenge",
                    rate=1.25,
                    note_counts={"taps": 90, "holds": 8, "rolls": 2, "total": 100},
                    rating=14.3, rice=13.0, calc_ms=42.7, total_ms=51.2,
                    subprocess_ms=31.4,
                    graph_points=350,
                    skillsets=["stream", "release"],
                    bridge=debug.bridge_health(
                        connection="ready", chart_rate=1.25,
                        now=10, menu_time=4000, menu_rate=1.25,
                        menu_received=9.98,
                    ),
                )
        text = (self.folder / "debug.log").read_text(encoding="utf-8")
        for expected in ("Engine: XDC1", "Rolls: 2", "Graph points: 350",
                         "Engine time: 42.7 ms", "XDC1 subprocess: 31.4 ms",
                         "Clock: Rate aligned",
                         "Top skillsets: stream, release"):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_engine_comparison_only_when_same_chart_and_rate(self):
        events = []
        with patch.object(debug, "enabled", True):
            with patch.object(debug, "emit", side_effect=events.append):
                with patch.object(debug, "_ratings", debug.OrderedDict()):
                    one = ("song.ssc", "Hard", "11", "", "dance-single", 1.0)
                    two = ("song.ssc", "Hard", "11", "", "dance-single", 1.25)
                    debug.remember_engine_rating(
                        one, "Legacy", 9.2, "Mid-Alpha")
                    self.assertEqual(events, [])
                    debug.remember_engine_rating(
                        two, "XDC1", 14.0, "Mid-Gamma")
                    self.assertEqual(events, [])
                    debug.remember_engine_rating(
                        one, "XDC1", 13.5, "Low-Gamma")
                    self.assertEqual(len(events), 1)
                    self.assertIn("different scales", events[0])
                    self.assertIn("9.200 SR", events[0])
                    self.assertIn("13.500 Dan", events[0])

    def test_error_traceback_is_logged_only_in_debug_mode(self):
        with patch.object(debug, "enabled", True):
            with patch.object(debug, "_log_path", None):
                debug.configure(self.folder)
                try:
                    raise ValueError("test timing exception")
                except ValueError as exc:
                    debug.report_error(exc, engine="XDC1",
                                       path="failed.ssc", total_ms=6.0)
        logs = (self.folder / "debug.log").read_text(encoding="utf-8")
        self.assertIn("[Calculation ERROR]", logs)
        self.assertIn("ValueError: test timing exception", logs)
        self.assertIn("Traceback", logs)


if __name__ == "__main__":
    unittest.main()

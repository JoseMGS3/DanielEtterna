"""Integration tests: XDC1 C++ CLI invoked via DanielEtterna's Python adapter."""
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import chart_loader
import dan_scale
import xdc1_adapter as adapter


def fixture_notes():
    # 4K stream with varying rhythms and real long notes.
    notes = []
    for i in range(160):
        head = 900 + 116 * i + 3 * (i % 6)
        end = head + 420 if i % 13 == 0 else -1
        notes.append((i % 4, head, end))
    return notes


class XDC1AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # This file is intended to run *after* compiling the real engine.
        # Never silently skip tests if the compiler output is missing.
        cls.binary = adapter.resolve_xdc1_binary()

    def test_compiled_engine_matches_direct_cli_json(self):
        notes = fixture_notes()
        output = adapter.analyze_notes(notes, executable=self.binary)
        raw_rows = "\n".join(f"{c} {h} {t}" for c, h, t in notes) + "\n"
        direct = subprocess.run(
            [str(self.binary), "--graph"],
            input=raw_rows, text=True, capture_output=True,
            check=True, timeout=45,
        )
        baseline = json.loads(direct.stdout)
        self.assertAlmostEqual(output["rating_points"], baseline["rating"], places=4)
        self.assertGreaterEqual(output["subprocess_ms"], 0.0)
        self.assertTrue(math.isfinite(output["subprocess_ms"]))
        self.assertAlmostEqual(
            output["rating_rice_points"], baseline["rating_rice"], places=4
        )
        self.assertEqual(output["skillsets_points"], baseline["skillsets"])
        self.assertEqual(output["grid"], baseline["grid"])
        self.assertEqual(output["graph_points"], baseline["graph"])
        self.assertEqual(set(output["skillsets"]), set(baseline["skillsets"]))
        self.assertEqual(len(output["skillsets"]), 7)
        self.assertEqual(len(output["grid"]), len(output["strain_rested"]))
        self.assertGreater(len(output["grid"]), 2)
        self.assertTrue(math.isfinite(output["rating"]))
        self.assertTrue(math.isfinite(output["rating_rice"]))
        self.assertAlmostEqual(
            output["rating"], dan_scale.to_dan(
                dan_scale.points_to_raw(baseline["rating"])
            ),
            places=8,
        )

    def test_negative_chart_offset_is_restored_on_graph_axis(self):
        notes = [
            (col, head - 2000, tail - 2000 if tail != -1 else -1)
            for col, head, tail in fixture_notes()
        ]
        payload, offset = adapter._prepare_input(notes)
        self.assertGreater(offset, 0)
        self.assertTrue(payload.startswith("0 0 "))
        direct = json.loads(subprocess.run(
            [str(self.binary), "--graph"], input=payload,
            text=True, capture_output=True, check=True, timeout=45,
        ).stdout)
        output = adapter.analyze_notes(notes, executable=self.binary)
        self.assertEqual(
            output["grid"],
            [float(t) - offset for t in direct["grid"]],
        )
        self.assertAlmostEqual(output["rating_points"], direct["rating"])

    def test_chart_convenience_api_supports_rate_and_ln_switch(self):
        notes = fixture_notes()
        data = {
            "format": "osu",
            "keycount": 4,
            "normalized_notes": notes,
        }
        direct = adapter.analyze_notes(
            chart_loader.rate_normalized_notes(notes, rate=1.25),
            executable=self.binary,
        )
        from_chart = adapter.analyze_chart(
            data, rate=1.25, executable=self.binary,
        )
        self.assertEqual(direct["rating_points"], from_chart["rating_points"])
        no_ln = adapter.analyze_chart(
            data, rate=1.25, include_long_notes=False,
            executable=self.binary,
        )
        self.assertAlmostEqual(
            no_ln["rating_points"], no_ln["rating_rice_points"], places=4,
        )
        self.assertEqual(len(no_ln["skillsets"]), 7)

    def test_input_format_is_validated_before_execution(self):
        cases = [
            [],
            [(0, 10, -1)],
            [(0, 1)],
            [(5, 10, -1), (0, 20, -1)],
            [(0, 15.5, -1), (1, 25, -1)],
            [(0, 20, 10), (1, 40, -1)],
        ]
        for notes in cases:
            with self.subTest(notes=notes):
                with self.assertRaises(ValueError):
                    adapter.analyze_notes(notes, executable=self.binary)

    def test_nonexistent_binary_is_clear_error(self):
        with self.assertRaises(FileNotFoundError):
            adapter.analyze_notes(
                fixture_notes(),
                executable=ROOT / "never-existent-xdc1",
            )

    def test_bad_json_is_reported(self):
        with patch.object(
            adapter.subprocess, "run",
            return_value=SimpleNamespace(
                returncode=0, stdout="{no-json", stderr=""
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "valid JSON"):
                adapter.analyze_notes(fixture_notes(), executable=self.binary)

    def test_engine_error_is_reported(self):
        with patch.object(
            adapter.subprocess, "run",
            return_value=SimpleNamespace(
                returncode=1, stdout="", stderr="invalid input"
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "invalid input"):
                adapter.analyze_notes(fixture_notes(), executable=self.binary)


if __name__ == "__main__":
    unittest.main()

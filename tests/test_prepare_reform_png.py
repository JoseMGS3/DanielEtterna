"""Regression tests for build-time conversion of Reform SVG Dan badges."""
import io
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from PIL import Image
import prepare_reform_png


class ReformConversionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)

    def make_svg_set(self):
        original = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024"/>'
        for level in range(1, 11):
            for suffix in ("-low", "-mid-low", "", "-mid-high", "-high"):
                (self.folder / f"{level}{suffix}.svg").write_text(
                    original, encoding="utf-8"
                )
        return original

    def test_all_50_svg_files_get_png_counterparts(self):
        original = self.make_svg_set()
        output = io.BytesIO()
        Image.new("RGBA", (8, 8), (190, 90, 60, 255)).save(output, "PNG")
        generated = []

        def fake_render(svg, fonts):
            self.assertIn('width="1024" height="1024"', svg)
            generated.append(svg)
            return output.getvalue()

        fake_module = types.SimpleNamespace(
            FontDatabase=lambda: object(),
            svg_to_png=fake_render,
        )
        with patch.dict(sys.modules, {"svg2png_py": fake_module}):
            number = prepare_reform_png.convert(self.folder)
        self.assertEqual(number, 50)
        self.assertEqual(len(generated), 50)
        self.assertEqual(len(list(self.folder.glob("*.png"))), 50)
        self.assertEqual(
            (self.folder / "10-high.svg").read_text(encoding="utf-8"),
            original,
        )
        with Image.open(self.folder / "10-high.png") as image:
            self.assertEqual(image.size, (8, 8))

    def test_missing_svg_aborts_instead_of_building_partial_set(self):
        fake_module = types.SimpleNamespace(FontDatabase=lambda: None)
        with patch.dict(sys.modules, {"svg2png_py": fake_module}):
            with self.assertRaises(FileNotFoundError):
                prepare_reform_png.convert(self.folder)
        self.assertFalse(list(self.folder.glob("*.png")))


if __name__ == "__main__":
    unittest.main()

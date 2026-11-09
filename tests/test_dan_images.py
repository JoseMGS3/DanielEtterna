"""GUI-free tests for optional image loading and caching."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, sentinel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image
import dan_image_renderer


class ImageTests(unittest.TestCase):
    def setUp(self):
        dan_image_renderer._IMAGE_CACHE.clear()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)

    def test_missing_art_is_safe(self):
        self.assertIsNone(dan_image_renderer.load_dan_image(None, 40))
        self.assertIsNone(dan_image_renderer.load_dan_image(
            self.folder / "missing.svg", 40
        ))

    def test_webp_cache_and_proportions(self):
        path = self.folder / "beta-low.webp"
        Image.new("RGB", (120, 40), (190, 50, 20)).save(path, "WEBP")
        sizes = []

        def fake_photo(img, master=None):
            sizes.append(img.size)
            return sentinel.artwork

        with patch.object(dan_image_renderer.ImageTk, "PhotoImage", fake_photo):
            a = dan_image_renderer.load_dan_image(path, 60)
            b = dan_image_renderer.load_dan_image(path, 60)
        self.assertIs(a, sentinel.artwork)
        self.assertIs(b, a)
        self.assertEqual(sizes, [(180, 60)])

    def test_invalid_webp_is_safe(self):
        path = self.folder / "bad.webp"
        path.write_bytes(b"invalid")
        self.assertIsNone(dan_image_renderer.load_dan_image(path, 40))


if __name__ == "__main__":
    unittest.main()

"""GUI-free tests for vertical text centering in Compact and Statistics."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src" / "daniel_etterna.py").read_text(encoding="utf-8")


def load_alignment_function():
    tree = ast.parse(SOURCE)
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_center_nonfull_text"
    )
    code = compile(
        ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
        "<alignment>", "exec",
    )
    namespace = {}
    exec(code, namespace)
    return namespace["_center_nonfull_text"]


class FakeCanvas:
    def __init__(self, height, boxes):
        self.height = height
        self.boxes = dict(boxes)
        self.moves = []

    def winfo_height(self):
        return self.height

    def bbox(self, *items):
        if not items:
            return None
        boxes = [self.boxes[i] for i in items if i in self.boxes]
        if not boxes:
            return None
        return (
            min(b[0] for b in boxes),
            min(b[1] for b in boxes),
            max(b[2] for b in boxes),
            max(b[3] for b in boxes),
        )

    def move(self, item, dx, dy):
        x0, y0, x1, y1 = self.boxes[item]
        self.boxes[item] = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        self.moves.append((item, dx, dy))


class VerticalTextAlignmentTests(unittest.TestCase):
    @staticmethod
    def apply(mode, height, boxes, dan, msd=()):
        align = load_alignment_function()
        canvas = FakeCanvas(height, boxes)
        namespace = align.__globals__
        namespace.update({
            "MODE_FULL": 2,
            "current_mode": mode,
            "canvas": canvas,
            "text_items": list(dan),
            "msd_items": list(msd),
            "_saved_mode_size": lambda unused_mode: (550, 72),
        })
        align()
        return canvas

    def test_compact_centers_dan_row_in_default_height(self):
        boxes = {
            "prefix": (14, 15, 134, 41),
            "dan": (143, 5, 305, 55),
            "number": (315, 15, 410, 41),
        }
        canvas = self.apply(0, 72, boxes, ["prefix", "dan", "number"])
        self.assertEqual(canvas.bbox("prefix", "dan", "number")[1:4:2], (11, 61))
        self.assertTrue(all(dx == 0 and dy == 6 for _, dx, dy in canvas.moves))
        self.assertEqual(canvas.boxes["prefix"][0], 14)

    def test_compact_recenters_when_height_changes(self):
        boxes = {"dan": (90, 5, 200, 55)}
        for height in (72, 102, 160):
            with self.subTest(height=height):
                canvas = self.apply(0, height, boxes, ["dan"])
                bounds = canvas.bbox("dan")
                self.assertLessEqual(abs((bounds[1] + bounds[3]) / 2 - height / 2), 0.5)

    def test_statistics_centers_dan_and_msd_together(self):
        boxes = {
            "prefix": (14, 14, 135, 45),
            "dan": (145, 5, 350, 55),
            "msd": (14, 66, 550, 100),
        }
        canvas = self.apply(1, 116, boxes, ["prefix", "dan"], ["msd"])
        bounds = canvas.bbox("prefix", "dan", "msd")
        self.assertLessEqual(abs((bounds[1] + bounds[3]) / 2 - 116 / 2), 0.5)
        self.assertEqual(canvas.boxes["msd"][1] - canvas.boxes["dan"][1], 61)
        self.assertTrue(any(item == "msd" for item, _, _ in canvas.moves))

    def test_statistics_without_msd_centers_only_dan(self):
        canvas = self.apply(1, 180, {"dan": (0, 10, 100, 50)}, ["dan"])
        self.assertEqual(canvas.bbox("dan")[1:4:2], (70, 110))

    def test_full_mode_keeps_existing_positions(self):
        boxes = {"dan": (90, 280, 350, 330), "msd": (14, 350, 500, 380)}
        canvas = self.apply(2, 407, boxes, ["dan"], ["msd"])
        self.assertEqual(canvas.boxes, boxes)
        self.assertEqual(canvas.moves, [])

    def test_update_dan_text_invokes_centering_after_msd_is_drawn(self):
        tree = ast.parse(SOURCE)
        fn = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "update_dan_text"
        )
        invoked = [
            node for node in ast.walk(fn)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_center_nonfull_text"
        ]
        self.assertEqual(len(invoked), 1)
        self.assertIn("def _center_nonfull_text():", SOURCE)


if __name__ == "__main__":
    unittest.main()

"""Convert the numbered Reform Dan SVG assets to PNG for Windows builds.

Creates 50 transparent PNG files next to the SVG originals. Original
SVG files are not modified; PNG files are bundled into the one-file EXE.
Requires: pip install svg2png-py
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "src" / "nomenclatures" / "images"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def convert(directory=IMAGE_DIR):
    import svg2png_py

    directory = Path(directory)
    svg_files = [
        directory / f"{level}{suffix}.svg"
        for level in range(1, 11)
        for suffix in ("-low", "-mid-low", "", "-mid-high", "-high")
    ]
    missing = [path.name for path in svg_files if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing Dan SVG assets: " + ", ".join(missing))

    fonts = svg2png_py.FontDatabase()
    for svg in svg_files:
        png = bytes(svg2png_py.svg_to_png(
            svg.read_text(encoding="utf-8"), fonts
        ))
        if not png.startswith(PNG_SIGNATURE):
            raise ValueError(f"Invalid PNG generated for {svg.name}")
        svg.with_suffix(".png").write_bytes(png)

    print(f"Generated {len(svg_files)} Reform PNG images.")
    return len(svg_files)


if __name__ == "__main__":
    try:
        convert()
    except Exception as exc:
        print(f"ERROR: Could not prepare Reform SVG images: {exc}", file=sys.stderr)
        sys.exit(1)

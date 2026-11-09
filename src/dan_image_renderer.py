"""Load and cache optional Reform Dan art on Tkinter canvases."""
from collections import OrderedDict
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageTk

_IMAGE_CACHE = OrderedDict()
_MAX_IMAGES = 48


def load_dan_image(path, height, master=None):
    if path is None:
        return None
    source = Path(path)
    height = max(12, min(250, int(height)))
    try:
        key = (str(source), source.stat().st_mtime_ns, height)
    except OSError:
        return None
    if key in _IMAGE_CACHE:
        _IMAGE_CACHE.move_to_end(key)
        return _IMAGE_CACHE[key]

    try:
        if source.suffix.lower() == ".svg":
            import cairosvg
            png = cairosvg.svg2png(bytestring=source.read_bytes(), output_height=height)
            art = Image.open(BytesIO(png)).convert("RGBA")
        elif source.suffix.lower() in (".webp", ".png"):
            with Image.open(source) as original:
                art = original.convert("RGBA")
        else:
            return None
        if art.height != height:
            width = max(1, round(art.width * height / art.height))
            art = art.resize((width, height), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(art, master=master)
    except Exception:
        return None

    _IMAGE_CACHE[key] = photo
    if len(_IMAGE_CACHE) > _MAX_IMAGES:
        _IMAGE_CACHE.popitem(last=False)
    return photo

"""Versioned, JSON-backed Dan nomenclatures for DanielEtterna.

Built-in templates are copied to the user's config folder on first use,
so custom edits survive application upgrades. The embedded fallback also
works in PyInstaller builds that do not bundle external JSON data.
"""
import json
import math
import re
from copy import deepcopy
from pathlib import Path

import config_manager


DEFAULT_NAME = "Default"
SCHEMA_VERSION = 1
BUILTIN_PROFILES = json.loads(r'''{
  "Default": {
    "schema_version": 1,
    "id": "Default",
    "name": "Default",
    "label_mode": "legacy",
    "numeric_offset": 0,
    "tiers": [
      "Low",
      "Mid",
      "High"
    ]
  },
  "MMA": {
    "schema_version": 1,
    "id": "MMA",
    "name": "MMA",
    "label_mode": "centered",
    "numeric_offset": 0,
    "tiers": [
      "low",
      "mid/low",
      "mid",
      "mid/high",
      "high"
    ],
    "dans": {
      "0": "Intro 3",
      "1": "Reform 1",
      "2": "Reform 2",
      "3": "Reform 3",
      "4": "Reform 4",
      "5": "Reform 5",
      "6": "Reform 6",
      "7": "Reform 7",
      "8": "Reform 8",
      "9": "Reform 9",
      "10": "Reform 10",
      "11": "Alpha",
      "12": "Beta",
      "13": "Gamma",
      "14": "Delta",
      "15": "Epsilon",
      "16": "Emik Zeta",
      "17": "Thaumiel Eta",
      "18": "CloverWisp Theta",
      "19": "Iota",
      "20": "Kappa",
      "-2": "Intro 1",
      "-1": "Intro 2"
    }
  },
  "PlusMinus": {
    "schema_version": 1,
    "id": "PlusMinus",
    "name": "--/++",
    "label_mode": "suffix",
    "numeric_offset": 0,
    "tiers": [
      "--",
      "-",
      "",
      "+",
      "++"
    ],
    "dans": {
      "1": "1",
      "2": "2",
      "3": "3",
      "4": "4",
      "5": "5",
      "6": "6",
      "7": "7",
      "8": "8",
      "9": "9",
      "10": "10",
      "11": "Alpha",
      "12": "Beta",
      "13": "Gamma",
      "14": "Delta",
      "15": "Epsilon",
      "16": "Emik Zeta",
      "17": "Thaumiel Eta",
      "18": "CloverWisp Theta",
      "19": "Iota",
      "20": "Kappa"
    }
  },
  "Mania tracker": {
    "schema_version": 1,
    "id": "Mania tracker",
    "name": "Mania tracker",
    "label_mode": "interval",
    "numeric_offset": 0,
    "tiers": [
      "low",
      "mid/low",
      "mid",
      "mid/high",
      "high"
    ],
    "dans": {
      "0": "Intro 3",
      "1": "Reform 1",
      "2": "Reform 2",
      "3": "Reform 3",
      "4": "Reform 4",
      "5": "Reform 5",
      "6": "Reform 6",
      "7": "Reform 7",
      "8": "Reform 8",
      "9": "Reform 9",
      "10": "Reform 10",
      "11": "Alpha",
      "12": "Beta",
      "13": "Gamma",
      "14": "Delta",
      "15": "Epsilon",
      "16": "Emik Zeta",
      "17": "Thaumiel Eta",
      "18": "CloverWisp Theta",
      "19": "Iota",
      "20": "Kappa",
      "-2": "Intro 1",
      "-1": "Intro 2"
    }
  },
  "Images": {
    "schema_version": 1,
    "id": "Images",
    "name": "Images",
    "label_mode": "interval",
    "numeric_offset": 0,
    "tiers": [
      "low",
      "mid/low",
      "mid",
      "mid/high",
      "high"
    ],
    "dans": {
      "0": "Intro 3",
      "1": "Reform 1",
      "2": "Reform 2",
      "3": "Reform 3",
      "4": "Reform 4",
      "5": "Reform 5",
      "6": "Reform 6",
      "7": "Reform 7",
      "8": "Reform 8",
      "9": "Reform 9",
      "10": "Reform 10",
      "11": "Alpha",
      "12": "Beta",
      "13": "Gamma",
      "14": "Delta",
      "15": "Epsilon",
      "16": "Emik Zeta",
      "17": "Thaumiel Eta",
      "18": "CloverWisp Theta",
      "19": "Iota",
      "20": "Kappa",
      "-2": "Intro 1",
      "-1": "Intro 2"
    }
  }
}''')
_VALID_FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,63}\Z")
# Slash is forbidden in Windows file names. Keep the requested user-facing
# nomenclature title while using a portable JSON filename.
_DISPLAY_TO_FILENAME = {"--/++": "PlusMinus"}

_IMAGE_CODES = {
    **{i: str(i) for i in range(1, 11)},
    **dict(enumerate((
        "alpha", "beta", "gamma", "delta", "epsilon",
        "zeta", "eta", "theta", "iota", "kappa",
    ), start=11)),
}
_IMAGE_TIERS = ("-low", "-mid-low", "", "-mid-high", "-high")


def nomenclatures_dir():
    return config_manager.get_config_dir() / "nomenclatures"


def images_dir():
    """Writable folder for images uploaded after installation."""
    return nomenclatures_dir() / "images"


def image_asset_directories():
    """Look for user uploads, repository assets and bundled EXE resources."""
    import sys

    roots = []
    if getattr(sys, "frozen", False):
        exe_folder = Path(sys.executable).resolve().parent
        roots.extend((exe_folder, exe_folder.parent))
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        roots.append(Path(bundle))
    roots.append(Path(__file__).resolve().parent)

    candidates = [images_dir()]
    for root in roots:
        candidates.extend((
            root / "nomenclatures" / "images",
            root / "src" / "nomenclatures" / "images",
        ))
    seen = set()
    result = []
    for folder in candidates:
        folder = folder.resolve()
        if folder not in seen:
            seen.add(folder)
            result.append(folder)
    return tuple(result)


def image_asset_status():
    """Number of supported rank files visible to the running app."""
    folders = image_asset_directories()
    found = 0
    total = 0
    for level, code in _IMAGE_CODES.items():
        extension = ".svg" if level <= 10 else ".webp"
        for suffix in _IMAGE_TIERS:
            total += 1
            filename = f"{code}{suffix}{extension}"
            if any((folder / filename).is_file() for folder in folders):
                found += 1
    return found, total


def image_asset_filename(dp):
    """Five subdivisions per integer Dan; never modifies the original DP."""
    if isinstance(dp, bool) or not isinstance(dp, (int, float)) or not math.isfinite(dp):
        return None
    value = round(float(dp), 2)
    level = math.floor(value)
    code = _IMAGE_CODES.get(level)
    if code is None:
        return None
    bucket = max(0, min(4, math.floor((value - level) * 5 + 1e-9)))
    ext = "svg" if level <= 10 else "webp"
    return f"{code}{_IMAGE_TIERS[bucket]}.{ext}"


def image_asset_path(dp):
    """Prefer local user images; fall back to source/bundled assets."""
    name = image_asset_filename(dp)
    if name is None:
        return None
    for folder in image_asset_directories():
        target = folder / name
        # At build time the 50 SVG graphics are rasterized into PNG,
        # avoiding any Cairo DLL requirement in the Windows executable.
        if target.suffix == ".svg":
            png = target.with_suffix(".png")
            if png.is_file():
                return png
        if target.is_file():
            return target
    return None


def _valid_name(name):
    return isinstance(name, str) and bool(_VALID_FILENAME.fullmatch(name))


def _valid_profile(data):
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        return False
    mode = data.get("label_mode")
    if mode == "legacy":
        return True
    if mode not in ("centered", "interval", "suffix"):
        return False
    try:
        offset = float(data["numeric_offset"])
        tiers = data["tiers"]
        dans = data["dans"]
    except (KeyError, TypeError, ValueError):
        return False
    return (
        math.isfinite(offset)
        and -5.0 <= offset <= 5.0
        and isinstance(tiers, list)
        and len(tiers) >= 2
        and (mode not in ("suffix", "interval") or len(tiers) == 5)
        and all(isinstance(t, str) for t in tiers)
        and (mode != "centered" or all(t.strip() for t in tiers))
        and isinstance(dans, dict)
        and all(isinstance(k, str) and isinstance(v, str) and v.strip()
                for k, v in dans.items())
    )


def _bundled_profile(name):
    # The checked-in JSON files are editable source templates. A compiled
    # executable may not include them, so retain a Python fallback.
    template = Path(__file__).resolve().parent / "nomenclatures" / (name + ".json")
    try:
        data = json.loads(template.read_text(encoding="utf-8"))
        if _valid_profile(data):
            return data
    except (OSError, ValueError, TypeError):
        pass
    return deepcopy(BUILTIN_PROFILES[name])


def ensure_builtin_files():
    folder = nomenclatures_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        images_dir().mkdir(parents=True, exist_ok=True)
        for name in BUILTIN_PROFILES:
            target = folder / (name + ".json")
            if not target.exists():
                target.write_text(
                    json.dumps(_bundled_profile(name), ensure_ascii=False, indent=2)
                    + "\n",
                    encoding="utf-8",
                )
    except OSError:
        # Fall back to built-in definitions if the folder is read-only.
        pass


def available_names():
    ensure_builtin_files()
    names = set(BUILTIN_PROFILES)
    try:
        names.update(
            item.stem for item in nomenclatures_dir().glob("*.json")
            if _valid_name(item.stem)
        )
    except OSError:
        pass
    # Display labels need not be valid filenames (e.g. "--/++").
    builtin_labels = ["Default", "MMA", "--/++", "Mania tracker", "Images"]
    return builtin_labels + sorted(names - set(BUILTIN_PROFILES))


def _normalize_legacy_builtin_profile(name, data):
    """Migrate old built-in classifications in memory, preserving user edits.

    Existing JSON files are not overwritten on update; an old MMA.json
    with a -0.5 offset would otherwise classify 12.0 as Beta low instead
    of Beta mid. Mania tracker also had an earlier centered-mode bug.
    """
    if (
        name == "MMA"
        and data.get("id") == "MMA"
        and data.get("label_mode") == "centered"
        and data.get("numeric_offset") == -0.5
    ):
        data = dict(data)
        data["numeric_offset"] = 0
    elif (
        name == "Mania tracker"
        and data.get("id") == "Mania tracker"
        and data.get("label_mode") == "centered"
        and data.get("numeric_offset") == 0
    ):
        data = dict(data)
        data["label_mode"] = "interval"
    return data


def load_profile(name):
    name = _DISPLAY_TO_FILENAME.get(name, name)
    if not _valid_name(name):
        name = DEFAULT_NAME
    ensure_builtin_files()
    try:
        data = json.loads(
            (nomenclatures_dir() / (name + ".json")).read_text(encoding="utf-8")
        )
        if _valid_profile(data):
            return _normalize_legacy_builtin_profile(name, data)
    except (OSError, ValueError, TypeError):
        pass
    if name in BUILTIN_PROFILES:
        return _bundled_profile(name)
    return _bundled_profile(DEFAULT_NAME)


def apply_nomenclature(default_label, default_numeric, name=DEFAULT_NAME):
    """Format an existing Daniel rating; never alter the underlying SR."""
    profile = load_profile(name)
    if profile["label_mode"] == "legacy":
        return default_label, default_numeric

    # The legacy estimator has no reliable numeric rating outside its
    # supported range; do not fabricate MMA/Intro or Iota/Kappa ratings.
    if (not isinstance(default_numeric, (int, float))
            or isinstance(default_numeric, bool)
            or not math.isfinite(default_numeric)
            or default_label.startswith("<")
            or default_label.startswith(">")
            or default_label == "? ? ? ? ?"):
        return default_label, default_numeric

    # Offset applies to label classification ONLY, never the displayed
    # numeric rating. This preserves the original estimator's reading.
    display_numeric = default_numeric
    label_numeric = round(float(default_numeric) + float(profile["numeric_offset"]), 2)
    mode = profile["label_mode"]
    # "interval" (Mania tracker) and "suffix" (--/++) divide each
    # unshifted integer Dan into five buckets: .00–.19 low, .20–.39
    # mid/low, .40–.59 mid, .60–.79 mid/high, .80–.99 high.
    integer_based = mode in ("suffix", "interval")
    base = (
        math.floor(label_numeric)
        if integer_based
        else math.floor(label_numeric + 0.5)
    )
    name_at_base = profile["dans"].get(str(base))
    if name_at_base is None:
        return default_label, default_numeric

    tiers = profile["tiers"]
    position = label_numeric - (base if integer_based else base - 0.5)
    index = min(len(tiers) - 1, max(0, math.floor(position * len(tiers) + 1e-9)))
    if mode == "suffix":
        return f"{name_at_base}{tiers[index]}", display_numeric
    return f"{name_at_base} {tiers[index]}", display_numeric


def color_key_from_label(label):
    """Keep the existing Dan palette for both naming formats."""
    tokens = set(re.split(r"[-+\s/]+", str(label)))
    for key in ("Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta"):
        if key in tokens:
            return key
    return None

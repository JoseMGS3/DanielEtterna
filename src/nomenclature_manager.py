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
    "numeric_offset": -0.5,
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
  }
}''')
_VALID_FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,63}\Z")
# Slash is forbidden in Windows file names. Keep the requested user-facing
# nomenclature title while using a portable JSON filename.
_DISPLAY_TO_FILENAME = {"--/++": "PlusMinus"}


def nomenclatures_dir():
    return config_manager.get_config_dir() / "nomenclatures"


def _valid_name(name):
    return isinstance(name, str) and bool(_VALID_FILENAME.fullmatch(name))


def _valid_profile(data):
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        return False
    mode = data.get("label_mode")
    if mode == "legacy":
        return True
    if mode not in ("centered", "suffix"):
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
        and (mode != "suffix" or len(tiers) == 5)
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
    builtin_labels = ["Default", "MMA", "--/++", "Mania tracker"]
    return builtin_labels + sorted(names - set(BUILTIN_PROFILES))


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
            return data
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

    numeric = round(float(default_numeric) + float(profile["numeric_offset"]), 2)
    mode = profile["label_mode"]
    # The --/++ profile keeps unshifted integer-based Dan ranges:
    # 9.0–9.2 = 9--, 9.2–9.4 = 9-, 9.4–9.6 = 9,
    # 9.6–9.8 = 9+, 9.8–10.0 = 9++.
    base = math.floor(numeric) if mode == "suffix" else math.floor(numeric + 0.5)
    name_at_base = profile["dans"].get(str(base))
    if name_at_base is None:
        return default_label, default_numeric

    tiers = profile["tiers"]
    position = numeric - (base if mode == "suffix" else base - 0.5)
    index = min(len(tiers) - 1, max(0, math.floor(position * len(tiers) + 1e-9)))
    if mode == "suffix":
        return f"{name_at_base}{tiers[index]}", numeric
    return f"{name_at_base} {tiers[index]}", numeric


def color_key_from_label(label):
    """Keep the existing Dan palette for both naming formats."""
    tokens = set(re.split(r"[-+\s/]+", str(label)))
    for key in ("Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta"):
        if key in tokens:
            return key
    return None

import json
import os
import re
from copy import deepcopy
from pathlib import Path

import i18n


DEFAULT_CONFIG = {
    "config_version": 9,
    "etterna_root": "",
    "language": i18n.DEFAULT_LANGUAGE,
    "layout": "full",
    "nomenclature": "Default",
    "difficulty_engine": "Legacy",
    "xdc1_column_layout": "standard",
    "include_long_notes": True,
    "main_window_geometry": "",
    "window_sizes": {
        "compact": {"width": 550, "height": 72},
        "statistics": {"width": 650, "height": 116},
        "full": {"width": 650, "height": 407},
    },
    "global_hotkeys": False,
    "settings_window_size": {
        "width": 680,
        "height": 720,
    },
    "keybinds": {
        "toggle_topmost": "F1",
        "cycle_mode": "Tab",
        "open_settings": "Q",
        "toggle_lns": "L",
    },
}


def get_config_dir():
    base = (
        os.environ.get("LOCALAPPDATA")
        or os.environ.get("APPDATA")
    )

    if base:
        return Path(base) / "DanielEtterna"

    return Path.home() / ".daniel_etterna"


def get_config_path():
    return get_config_dir() / "config.json"


# Dimensions used before v8. Only known 50/75/100% presets are migrated,
# preserving genuinely custom sizes selected by the user.
_LEGACY_LAYOUT_SIZES = {
    "compact": (550, 102),
    "statistics": (650, 157),
}
_LEGACY_PRESET_SCALES = (0.5, 0.75, 1.0)


def _migrate_legacy_preset_size(layout, width, height, source_version):
    if source_version >= 8 or layout not in _LEGACY_LAYOUT_SIZES:
        return width, height
    old_width, old_height = _LEGACY_LAYOUT_SIZES[layout]
    new_height = DEFAULT_CONFIG["window_sizes"][layout]["height"]
    for scale in _LEGACY_PRESET_SCALES:
        old_size = (
            int(old_width * scale + 0.5),
            int(old_height * scale + 0.5),
        )
        if (width, height) == old_size:
            return width, int(new_height * scale + 0.5)
    return width, height


def _merge_defaults(data):
    result = deepcopy(DEFAULT_CONFIG)

    if not isinstance(data, dict):
        return result

    # Version 2 changed the default Options hotkey from Ctrl+Tab to 1.
    # Existing v1 configs are migrated once, while future user changes
    # remain untouched.
    try:
        source_version = int(data.get("config_version", 1))
    except (TypeError, ValueError):
        source_version = 1

    etterna_root = data.get("etterna_root")
    if isinstance(etterna_root, str):
        result["etterna_root"] = etterna_root

    result["language"] = i18n.normalize_language(
        data.get("language", i18n.DEFAULT_LANGUAGE)
    )

    layout = str(data.get("layout", "full")).strip().lower()
    if layout in ("compact", "statistics", "full"):
        result["layout"] = layout

    # Keep the selected file name across updates. Invalid/missing profiles
    # are handled safely by the nomenclature manager.
    nomenclature = data.get("nomenclature")
    if isinstance(nomenclature, str) and nomenclature.strip():
        result["nomenclature"] = nomenclature.strip()

    # Default to the old engine for every existing installation. Do not
    # persist unexpected values from modified or outdated configs.
    engine = data.get("difficulty_engine")
    if engine in ("Legacy", "XDC1"):
        result["difficulty_engine"] = engine

    # Physical key layouts only affect XDC1; old installs keep the original grouping.
    column_layout = data.get("xdc1_column_layout")
    if column_layout in ("standard", "wasd"):
        result["xdc1_column_layout"] = column_layout

    # Existing installations keep LNs enabled until the user toggles them.
    include_long_notes = data.get("include_long_notes")
    if isinstance(include_long_notes, bool):
        result["include_long_notes"] = include_long_notes

    # Each layout keeps its own user-defined dimensions.
    saved_sizes = data.get("window_sizes")
    if isinstance(saved_sizes, dict):
        for name, defaults in result["window_sizes"].items():
            incoming = saved_sizes.get(name)
            if not isinstance(incoming, dict):
                continue
            try:
                width = int(incoming["width"])
                height = int(incoming["height"])
            except (KeyError, ValueError, TypeError, OverflowError):
                continue
            width, height = _migrate_legacy_preset_size(
                name, width, height, source_version
            )
            result["window_sizes"][name] = {
                "width": max(int(defaults["width"] * 0.5 + 0.5), min(width, 3840)),
                "height": max(int(defaults["height"] * 0.5 + 0.5), min(height, 2160)),
            }

    # Stored by Tk itself, so negative multi-monitor coordinates survive.
    window_geometry = data.get("main_window_geometry")
    if isinstance(window_geometry, str) and re.fullmatch(
        r"\d+x\d+(?:[+-]-?\d+[+-]-?\d+)?", window_geometry
    ):
        # The active window's saved geometry can otherwise restore an old
        # oversized preset even after updating window_sizes.
        match = re.match(r"(\d+)x(\d+)(.*)", window_geometry)
        width, height = int(match.group(1)), int(match.group(2))
        _, migrated_height = _migrate_legacy_preset_size(
            result["layout"], width, height, source_version
        )
        result["main_window_geometry"] = (
            f"{width}x{migrated_height}{match.group(3)}"
        )

    global_hotkeys = data.get("global_hotkeys")
    if isinstance(global_hotkeys, bool):
        result["global_hotkeys"] = global_hotkeys

    settings_window_size = data.get(
        "settings_window_size"
    )
    if isinstance(
        settings_window_size,
        dict
    ):
        try:
            width = int(
                settings_window_size.get(
                    "width",
                    680
                )
            )
            height = int(
                settings_window_size.get(
                    "height",
                    720
                )
            )
        except (TypeError, ValueError):
            width = 680
            height = 720

        result["settings_window_size"] = {
            "width": max(
                540,
                min(width, 3840)
            ),
            "height": max(
                620,
                min(height, 2160)
            ),
        }

    keybinds = data.get("keybinds")
    if isinstance(keybinds, dict):
        for key in result["keybinds"]:
            value = keybinds.get(key)
            if isinstance(value, str) and value.strip():
                result["keybinds"][key] = value.strip()

    if (
        source_version < 2
        and result["keybinds"].get("open_settings", "").lower() == "ctrl+tab"
    ):
        result["keybinds"]["open_settings"] = "1"

    # Version 3 fixes a capture bug where Tk could falsely report Alt as
    # pressed for ordinary keys. Repair the three known default shortcuts if
    # they were saved by that buggy build.
    if source_version < 3:
        repairs = {
            "Alt+Tab": "Tab",
            "Alt+F2": "F2",
            "Alt+1": "1",
        }
        for action, value in list(result["keybinds"].items()):
            result["keybinds"][action] = repairs.get(value, value)

    result["config_version"] = DEFAULT_CONFIG["config_version"]

    return result


def load_config():
    path = get_config_path()

    if not path.exists():
        return deepcopy(DEFAULT_CONFIG)

    try:
        data = json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return deepcopy(DEFAULT_CONFIG)

    return _merge_defaults(data)


def save_config(config):
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    clean = _merge_defaults(config)

    temp_path = path.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(
            clean,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    temp_path.replace(path)


_KEY_ALIASES = {
    "tab": "Tab",
    "escape": "Escape",
    "esc": "Escape",
    "space": "space",
    "enter": "Return",
    "return": "Return",
    "backspace": "BackSpace",
    "delete": "Delete",
    "del": "Delete",
    "insert": "Insert",
    "ins": "Insert",
    "home": "Home",
    "end": "End",
    "pageup": "Prior",
    "pgup": "Prior",
    "pagedown": "Next",
    "pgdn": "Next",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "plus": "plus",
    "minus": "minus",
    "equal": "equal",
    "comma": "comma",
    "period": "period",
    "slash": "slash",
    "backslash": "backslash",
    "semicolon": "semicolon",
    "apostrophe": "apostrophe",
    "bracketleft": "bracketleft",
    "bracketright": "bracketright",
    "grave": "grave",
}


def keybind_to_tk(spec, language=i18n.DEFAULT_LANGUAGE):
    """
    Convierte formatos amigables como:
        Tab
        F2
        Ctrl+Tab
        Ctrl+Shift+M
        Alt+O

    al formato de eventos de Tkinter.
    """

    if not isinstance(spec, str):
        raise ValueError(
            i18n.t("keybind_must_text", language)
        )

    raw_parts = [
        part.strip()
        for part in spec.split("+")
        if part.strip()
    ]

    if not raw_parts:
        raise ValueError(
            i18n.t("keybind_empty", language)
        )

    modifiers = []
    key = None

    for part in raw_parts:
        low = part.lower()

        if low in ("ctrl", "control"):
            if "Control" not in modifiers:
                modifiers.append("Control")
            continue

        if low == "shift":
            if "Shift" not in modifiers:
                modifiers.append("Shift")
            continue

        if low in ("alt", "option"):
            if "Alt" not in modifiers:
                modifiers.append("Alt")
            continue

        if key is not None:
            raise ValueError(
                i18n.t(
                    "invalid_keybind",
                    language,
                    spec=spec,
                )
            )

        if low in _KEY_ALIASES:
            key = _KEY_ALIASES[low]

        elif (
            low.startswith("f")
            and low[1:].isdigit()
            and 1 <= int(low[1:]) <= 24
        ):
            key = low.upper()

        elif len(part) == 1:
            key = part.lower()

        else:
            raise ValueError(
                i18n.t(
                    "unknown_key",
                    language,
                    key=part,
                )
            )

    if key is None:
        raise ValueError(
            i18n.t(
                "missing_key",
                language,
                spec=spec,
            )
        )

    pieces = modifiers + [key]
    return "<" + "-".join(pieces) + ">"


def validate_etterna_root(
    path_value,
    language=i18n.DEFAULT_LANGUAGE,
):
    raw = str(path_value or "").strip()

    if not raw:
        return False, i18n.t(
            "select_etterna_root",
            language,
        )

    path = Path(raw).expanduser()

    if not path.exists():
        return False, i18n.t(
            "folder_missing",
            language,
        )

    if not path.is_dir():
        return False, i18n.t(
            "not_folder",
            language,
        )

    if not (path / "Save").is_dir():
        return False, i18n.t(
            "save_missing",
            language,
        )

    return True, i18n.t(
        "valid_path",
        language,
    )

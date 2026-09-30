import json
import os
from copy import deepcopy
from pathlib import Path

import i18n


DEFAULT_CONFIG = {
    "config_version": 7,
    "etterna_root": "",
    "language": i18n.DEFAULT_LANGUAGE,
    "layout": "full",
    "global_hotkeys": False,
    "settings_window_size": {
        "width": 680,
        "height": 720,
    },
    "main_window_geometry": None,
    "keybinds": {
        "toggle_topmost": "F1",
        "cycle_mode": "Tab",
        "open_settings": "Q",
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

    global_hotkeys = data.get("global_hotkeys")
    if isinstance(global_hotkeys, bool):
        result["global_hotkeys"] = global_hotkeys

    main_window_geometry = data.get(
        "main_window_geometry"
    )
    if isinstance(
        main_window_geometry,
        dict
    ):
        try:
            main_width = int(
                main_window_geometry.get(
                    "width",
                    650
                )
            )
            main_height = int(
                main_window_geometry.get(
                    "height",
                    370
                )
            )
            main_x = int(
                main_window_geometry.get(
                    "x",
                    0
                )
            )
            main_y = int(
                main_window_geometry.get(
                    "y",
                    0
                )
            )
        except (TypeError, ValueError):
            main_width = 650
            main_height = 370
            main_x = 0
            main_y = 0

        result["main_window_geometry"] = {
            "width": max(
                350,
                min(main_width, 7680)
            ),
            "height": max(
                65,
                min(main_height, 4320)
            ),
            "x": max(
                -20000,
                min(main_x, 20000)
            ),
            "y": max(
                -20000,
                min(main_y, 20000)
            ),
        }

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

import os
import sys
import json
import time
import threading
import ctypes
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from pathlib import Path

import numpy as np
# import websocket

import algorithm
import chart_loader
import config_manager
import i18n
import global_hotkeys

from graph_fast import FastGraph


def resource_path(relative_path):
    """Get absolute path to resource — works for dev and when compiled with PyInstaller."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


# --- Constants ---

TOSU_WS = "ws://localhost:24050/ws"

# ============================================================
# ETTERNA
# ============================================================

# La ruta de Etterna ya no está fija en el código.
# Se carga desde:
#   %LOCALAPPDATA%\DanielEtterna\config.json
APP_CONFIG = config_manager.load_config()
current_language = i18n.normalize_language(
    APP_CONFIG.get("language", i18n.DEFAULT_LANGUAGE)
)

ETTERNA_ROOT = None
BRIDGE_FILE = None
GAMEPLAY_FILE = None
MENU_FILE = None

# Se incrementa cada vez que cambia la ruta para forzar
# a los bridges a releer el estado aunque el chart sea el mismo.
bridge_config_revision = 0

BREAK_ZERO_THRESHOLD_MS = 400
TIME_JUMP_THRESHOLD_MS = 2000
_OSU_TIMEOUT = 1.0

MODE_COMPACT = 0
MODE_STATISTICS = 1
MODE_FULL = 2
MODE_NAMES = ["compact", "statistics", "full"]

GRAPH_HEIGHT = 250
BAR_HEIGHT = 120
WINDOW_WIDTH = 650

COMPACT_HEIGHT = 65
STATISTICS_HEIGHT = 120
FULL_HEIGHT = GRAPH_HEIGHT + BAR_HEIGHT

COMPACT_WIDTH = 550
STATISTICS_WIDTH = 650
FULL_WIDTH = 650

MODE_HEIGHTS = {
    MODE_COMPACT: COMPACT_HEIGHT,
    MODE_STATISTICS: STATISTICS_HEIGHT,
    MODE_FULL: FULL_HEIGHT,
}
MODE_WIDTHS = {
    MODE_COMPACT: COMPACT_WIDTH,
    MODE_STATISTICS: STATISTICS_WIDTH,
    MODE_FULL: FULL_WIDTH,
}

BG_COLOR = "#000000"
PREFIX_FILL = "#FFFFFF"
DOT_RED = "#FF3B3B"
DOT_GREEN = "#00E676"

FONT_SCALE = float(os.environ.get("DANIEL_FONT_SCALE", "1.0" if os.name == "nt" else "0.67"))


def _font_size(size):
    return max(8, int(round(size * FONT_SCALE)))


FONT_PREFIX = ("Segoe UI Semibold", _font_size(30))
FONT_DAN = ("Segoe UI Bold", _font_size(45))
FONT_MSD_SKILL = ("Segoe UI Semibold", _font_size(29))
FONT_CONNECTION = ("Segoe UI Semibold", _font_size(18))

PREFIX_Y_OFFSET = 4.1
MSD_RELEVANCE_FRACTION = 0.15
VIBRO_JACKSPEED_THRESHOLD = 0.90

DAN_COLORS = {
    "Alpha":   "#ff5a5a",
    "Beta":    "#ffd84d",
    "Gamma":   "#00ffd5",
    "Delta":   "#ff7b00",
    "Epsilon": "#ff7a9e",
    "Zeta":    "#D7F7FF",
    "Eta":     "#ff2b2b",
    "Theta":   "#CC00FF",
}

DAN_MEANS = {
    "Alpha":   6.562,
    "Beta":    6.957,
    "Gamma":   7.459,
    "Delta":   7.939,
    "Epsilon": 9.095,
    "Zeta":    9.473,
    "Eta":     10.162,
    "Theta":   10.782,
}
ORDER = list(DAN_MEANS.keys())
DAN_ORDER_START = 11


# --- State ---

lock = threading.Lock()

current_map = None
current_mod = "NM"

current_difficulty = ""
current_meter = ""
current_description = ""
current_rate = 1.0

gameplay_music_ms = 0.0
gameplay_receive_time = 0.0
gameplay_rate = 1.0
gameplay_active = False

menu_music_ms = 0.0
menu_sample_start_ms = 0.0
menu_receive_time = 0.0
menu_rate = 1.0

gameplay_prev_music_ms = None
gameplay_is_moving = False

last_state = None
current_song_time_ms = 0

_ws_receive_time = 0.0
_ws_song_time_ms = 0
_prev_song_time_ms = 0
_prev_receive_time = 0.0
_last_message_time = 0.0

_paused = False
_pause_time_ms = 0
_frozen_interp_ms = 0.0

loading = False
loading_step = 0
_last_loading_dot = 0.0

current_strain_data = None
current_msd_data = None
current_native_msd = None

connection_phase = "connecting"

_last_dan_label = "."
_last_dan_numeric = ""
current_mode = MODE_FULL

# Estado de la ventana.
always_on_top = True
_resize_job = None

# Configuración editable desde el menú de opciones.
current_keybinds = dict(
    APP_CONFIG.get(
        "keybinds",
        config_manager.DEFAULT_CONFIG["keybinds"]
    )
)
_bound_key_sequences = {}
_settings_window = None

# Global keyboard hook. On Windows this keeps shortcuts working
# even while Etterna has focus.
hotkey_manager = global_hotkeys.GlobalHotkeyManager()
_local_key_dispatch_installed = False


def _set_etterna_root(path_value):
    """
    Actualiza en caliente la carpeta raíz de Etterna y las
    rutas de los tres archivos bridge.
    """
    global ETTERNA_ROOT
    global BRIDGE_FILE
    global GAMEPLAY_FILE
    global MENU_FILE
    global bridge_config_revision
    global connection_phase
    global last_state
    global current_map
    global current_native_msd
    global current_strain_data
    global current_msd_data
    global gameplay_active
    global gameplay_receive_time
    global menu_receive_time

    raw = str(path_value or "").strip()

    if raw:
        root_path = Path(raw).expanduser()

        ETTERNA_ROOT = root_path
        BRIDGE_FILE = (
            root_path
            / "Save"
            / "DanielBridge.txt"
        )
        GAMEPLAY_FILE = (
            root_path
            / "Save"
            / "DanielGameplay.txt"
        )
        MENU_FILE = (
            root_path
            / "Save"
            / "DanielMenu.txt"
        )

        valid, _ = (
            config_manager
            .validate_etterna_root(
                root_path,
                current_language
            )
        )

        connection_phase = (
            "connecting"
            if valid
            else "needs_config"
        )

    else:
        ETTERNA_ROOT = None
        BRIDGE_FILE = None
        GAMEPLAY_FILE = None
        MENU_FILE = None
        connection_phase = "needs_config"

    bridge_config_revision += 1
    last_state = None

    # No conservar datos del juego anterior al cambiar ruta.
    current_map = None
    current_native_msd = None
    current_strain_data = None
    current_msd_data = None
    gameplay_active = False
    gameplay_receive_time = 0.0
    menu_receive_time = 0.0


_set_etterna_root(
    APP_CONFIG.get(
        "etterna_root",
        ""
    )
)


# --- Window setup ---

if os.name == "nt" and hasattr(ctypes, "windll"):
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

root = tk.Tk()
root.tk.call("tk", "scaling", 1.0)
root.title("DanielEtterna")
root.geometry(f"{WINDOW_WIDTH}x{FULL_HEIGHT}")
root.resizable(True, True)

# Permitimos reducir la ventana sin romper el modo compacto.
root.minsize(350, BAR_HEIGHT + 80)

root.configure(bg=BG_COLOR)
root.attributes("-topmost", True)


def _set_dark_title_bar(window):
    try:
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass
    try:
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass


root.update_idletasks()
_set_dark_title_bar(root)

_icon_path = resource_path("icon.ico")
if os.path.exists(_icon_path):
    try:
        root.iconbitmap(_icon_path)
    except Exception:
        pass

_icon_png_path = resource_path("icon.png")
if os.path.exists(_icon_png_path):
    try:
        _icon_img = tk.PhotoImage(file=_icon_png_path)
        root.iconphoto(True, _icon_img)
    except Exception:
        pass

canvas = tk.Canvas(root, width=WINDOW_WIDTH, height=FULL_HEIGHT, bg=BG_COLOR, highlightthickness=0)
canvas.pack(expand=True, fill="both")

graph = FastGraph(canvas, GRAPH_HEIGHT, WINDOW_WIDTH)

text_items = []
msd_items = []
accent_bar = None
current_bar_color = "#333333"
_connection_items = []
_pulse_job = None


# --- Drawing helpers ---

def rgb(hex_color):
    r, g, b = root.winfo_rgb(hex_color)
    return r // 256, g // 256, b // 256


def lerp_color(c1, c2, t):
    r1, g1, b1 = rgb(c1)
    r2, g2, b2 = rgb(c2)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def draw_text(x, y, text, fill, font, anchor="w"):
    return [canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor)]


def draw_outline_text(x, y, text, fill, outline, font):
    items = []
    for ox, oy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
        items.append(canvas.create_text(x + ox, y + oy, text=text, fill=outline, font=font, anchor="w"))
    items.append(canvas.create_text(x, y, text=text, fill=fill, font=font, anchor="w"))
    return items


def is_loading_text(text):
    return text in (".", "..", "...")


def _get_text_y_offset():
    # En modo full el texto debe comenzar justo debajo del
    # gráfico, incluso después de redimensionar la ventana.
    return graph.graph_height if current_mode == MODE_FULL else 0


# --- Connection screen ---

def _draw_connection_screen():
    global _connection_items, _pulse_job

    if _pulse_job is not None:
        root.after_cancel(_pulse_job)
        _pulse_job = None

    for item in _connection_items:
        canvas.delete(item)
    _connection_items.clear()

    if connection_phase == "ready":
        return

    cy = max(1, canvas.winfo_height()) // 2

    if connection_phase == "needs_config":
        label = i18n.t("configure_path", current_language)
        dot_color = "#FFD84D"

    elif connection_phase == "connecting":
        label = i18n.t("waiting_bridge", current_language)
        dot_color = DOT_RED

    else:
        label = i18n.t("waiting_chart", current_language)
        dot_color = DOT_GREEN

    dot_r = 6
    dot_cx = 20
    inner = canvas.create_oval(
        dot_cx - dot_r, cy - dot_r,
        dot_cx + dot_r, cy + dot_r,
        fill=dot_color, outline="",
    )
    title = canvas.create_text(
        dot_cx + dot_r + 10, cy,
        text=label, fill="#AAAAAA",
        font=FONT_CONNECTION, anchor="w",
    )
    _connection_items += [inner, title]
    _pulse_connection(inner, dot_color, 0)


def _pulse_connection(inner, dot_color, step):
    global _pulse_job

    if connection_phase == "ready":
        _pulse_job = None
        return

    phase = (step % 40) / 40
    alpha = 0.4 + 0.6 * abs(1 - 2 * phase)
    pulsed = lerp_color("#000000", dot_color, alpha)
    canvas.itemconfig(inner, fill=pulsed)
    _pulse_job = root.after(50, lambda: _pulse_connection(inner, dot_color, step + 1))


def _clear_connection_screen():
    global _connection_items, _pulse_job

    if _pulse_job is not None:
        root.after_cancel(_pulse_job)
        _pulse_job = None

    for item in _connection_items:
        canvas.delete(item)
    _connection_items.clear()

    if current_mode == MODE_FULL and _last_dan_label not in ("Invalid Beatmap", ".", "..", "..."):
        graph.show()


def _clear_normal_ui():
    global text_items, msd_items, accent_bar

    for item in text_items:
        canvas.delete(item)
    text_items.clear()

    for item in msd_items:
        canvas.delete(item)
    msd_items.clear()

    if accent_bar:
        canvas.delete(accent_bar)
        accent_bar = None

    graph.hide()


def _clear_invalid_ui():
    global msd_items
    for item in msd_items:
        canvas.delete(item)
    msd_items.clear()
    graph.hide()


# --- UI components ---

def get_relevant_skillsets(msd_result):
    overall = msd_result.get("overall", 0)
    threshold = overall * MSD_RELEVANCE_FRACTION
    relevant = {k: v for k, v in msd_result.items() if k != "overall" and (overall - v) <= threshold}
    top3 = sorted(relevant.items(), key=lambda x: x[1], reverse=True)[:3]
    jackspeed = msd_result.get("jackspeed", 0)
    is_vibro = (overall > 0) and (jackspeed / overall >= VIBRO_JACKSPEED_THRESHOLD)
    return overall, top3, is_vibro


def draw_msd(msd_result, color):
    global msd_items
    for item in msd_items:
        canvas.delete(item)
    msd_items.clear()

    if current_mode == MODE_COMPACT:
        return

    if msd_result is None:
        y = _get_text_y_offset() + 80
        msd_items += draw_text(
            14,
            y,
            i18n.t("msd_error", current_language),
            "#FF4444",
            FONT_MSD_SKILL
        )
        return

    overall, top3, _ = get_relevant_skillsets(msd_result)
    if not top3:
        return

    skillset_str = ", ".join(key.capitalize() for key, _ in top3)
    y = _get_text_y_offset() + 80
    msd_items += draw_text(14, y, f"{skillset_str}  {overall:.2f}MSD", "#FFFFFF", FONT_MSD_SKILL)


def draw_accent_bar():
    global accent_bar
    if accent_bar:
        canvas.delete(accent_bar)
    h = max(1, canvas.winfo_height())
    accent_bar = canvas.create_rectangle(0, 0, 6, h, fill=current_bar_color, outline="")
    return accent_bar


def fade_items(text_item, bar_item, start_color, end_color, steps=14):
    global current_bar_color

    def _step(i):
        global current_bar_color
        if i < steps:
            color = lerp_color(start_color, end_color, i / steps)
            canvas.itemconfig(text_item, fill=color)
            canvas.itemconfig(bar_item, fill=color)
            current_bar_color = color
            root.after(15, lambda: _step(i + 1))
        else:
            canvas.itemconfig(text_item, fill=end_color)
            canvas.itemconfig(bar_item, fill=end_color)
            current_bar_color = end_color
            if current_mode == MODE_FULL:
                graph.set_color(end_color)

    _step(0)


def update_dan_text(dan_label, dan_numeric):
    global text_items, current_bar_color

    if connection_phase != "ready":
        return

    for item in text_items:
        canvas.delete(item)
    text_items.clear()

    if is_loading_text(dan_label):
        fill = "#888888"
        new_bar_color = "#333333"
    elif dan_label.startswith("<"):
        fill = "#7DF0FF"
        new_bar_color = fill
    else:
        if "-" in dan_label:
            base = dan_label.split("-", 1)[1]
        else:
            base = dan_label

        fill = DAN_COLORS.get(
            base,
            "#FFFFFF"
        )

        new_bar_color = fill

    bar = draw_accent_bar()
    y_off = _get_text_y_offset()
    y = y_off + 28
    prefix_y = y + PREFIX_Y_OFFSET

    prefix = draw_text(
        14,
        prefix_y,
        i18n.t("estimated_dan", current_language),
        PREFIX_FILL,
        FONT_PREFIX
    )
    text_items.extend(prefix)

    bbox = canvas.bbox(prefix[-1])
    pw = bbox[2] - bbox[0] if bbox else 0
    xpos = 14 + pw + 8

    is_vibro = False
    if (
        not is_loading_text(dan_label)
        and dan_label not in ("Invalid Beatmap", "? ? ? ? ?")
        and current_msd_data is not None
    ):
        _, _, is_vibro = get_relevant_skillsets(current_msd_data)

    if dan_label == "? ? ? ? ?":
        dan_items = draw_outline_text(xpos, y, dan_label, fill="#000000", outline="#FFFFFF", font=FONT_DAN)
        new_bar_color = "#FFFFFF"
    elif is_vibro:
        dan_items = draw_text(xpos, y, "VIBRO", "#FFFFFF", FONT_DAN)
        new_bar_color = "#FFFFFF"
    else:
        display_label = (
            i18n.t("invalid_beatmap", current_language)
            if dan_label == "Invalid Beatmap"
            else dan_label
        )
        dan_items = draw_text(
            xpos,
            y,
            display_label,
            current_bar_color,
            FONT_DAN
        )

    text_items.extend(dan_items)

    if not is_loading_text(dan_label) and dan_numeric not in ("", None):
        dan_bbox = canvas.bbox(dan_items[-1])
        numeric_x = (dan_bbox[2] if dan_bbox else xpos) + 10
        display_numeric = "N/A" if is_vibro else f"({dan_numeric})"
        text_items.extend(draw_text(numeric_x, prefix_y, display_numeric, "#FFFFFF", FONT_PREFIX))

    if current_mode != MODE_COMPACT:
        draw_msd(current_msd_data, new_bar_color if not is_loading_text(dan_label) else "#333333")
    else:
        for item in msd_items:
            canvas.delete(item)
        msd_items.clear()

    if current_mode == MODE_FULL:
        graph.set_color(
            new_bar_color if (is_loading_text(dan_label) or dan_label == "? ? ? ? ?") else current_bar_color
        )

    if not is_loading_text(dan_label) and dan_label != "? ? ? ? ?":
        fade_items(dan_items[-1], bar, current_bar_color, new_bar_color)
    else:
        canvas.itemconfig(bar, fill=new_bar_color)
        current_bar_color = new_bar_color
        if dan_label != "? ? ? ? ?":
            canvas.itemconfig(dan_items[-1], fill=fill)


def set_dan_text(label, numeric):
    root.after(0, lambda: update_dan_text(label, numeric))


# ============================================================
# WINDOW RESIZE
# ============================================================

def _rebuild_graph(width, height):
    """
    FastGraph usa un PhotoImage de tamaño fijo.

    Para poder redimensionar la ventana sin tocar graph_fast.py,
    destruimos únicamente la representación gráfica y la
    reconstruimos con el nuevo tamaño, conservando los datos
    de strain y el color actual.
    """
    global graph

    width = max(1, int(width))
    height = max(80, int(height))

    # No reconstruir si el tamaño efectivo no cambió.
    if (
        graph.window_width == width
        and graph.graph_height == height
    ):
        return

    try:
        graph.destroy()
    except Exception:
        pass

    graph = FastGraph(
        canvas,
        height,
        width
    )

    # Restaurar los datos que ya estaban calculados.
    strain_data = current_strain_data

    if (
        strain_data is not None
        and len(strain_data) == 2
        and len(strain_data[0]) >= 2
    ):
        graph.set_data(
            strain_data[0],
            strain_data[1]
        )

    graph.set_color(
        current_bar_color
    )

    if (
        current_mode == MODE_FULL
        and connection_phase == "ready"
        and _last_dan_label not in (
            "Invalid Beatmap",
            ".",
            "..",
            "..."
        )
    ):
        graph.show()
    else:
        graph.hide()


def _resize_contents():
    global _resize_job

    _resize_job = None

    width = max(
        1,
        canvas.winfo_width()
    )

    height = max(
        1,
        canvas.winfo_height()
    )

    if current_mode == MODE_FULL:
        graph_height = max(
            80,
            height - BAR_HEIGHT
        )

        _rebuild_graph(
            width,
            graph_height
        )

    if connection_phase != "ready":
        _draw_connection_screen()
    else:
        update_dan_text(
            _last_dan_label,
            _last_dan_numeric
        )


def _on_window_resize(event):
    global _resize_job

    # <Configure> también puede llegar desde widgets hijos.
    if event.widget is not root:
        return

    if _resize_job is not None:
        try:
            root.after_cancel(
                _resize_job
            )
        except Exception:
            pass

    # Debounce para no reconstruir FastGraph cientos de veces
    # mientras el usuario arrastra una esquina.
    _resize_job = root.after(
        80,
        _resize_contents
    )


# --- Mode switching ---

def _apply_mode():
    h = MODE_HEIGHTS[current_mode]
    w = MODE_WIDTHS[current_mode]

    min_height = {
        MODE_COMPACT: COMPACT_HEIGHT,
        MODE_STATISTICS: STATISTICS_HEIGHT,
        MODE_FULL: BAR_HEIGHT + 80,
    }[current_mode]

    root.minsize(
        350,
        min_height
    )

    root.geometry(f"{w}x{h}")
    canvas.configure(width=w, height=h)

    if current_mode == MODE_FULL:
        graph.show()
    else:
        graph.hide()

    if connection_phase != "ready":
        _draw_connection_screen()
    else:
        update_dan_text(
            _last_dan_label,
            _last_dan_numeric
        )

    # La geometría se aplica de forma asíncrona en Tk.
    root.after(
        100,
        _resize_contents
    )


def cycle_mode(event=None):
    global current_mode

    current_mode = (
        current_mode + 1
    ) % 3

    _apply_mode()

    print(
        f"[Mode] Switched to "
        f"{MODE_NAMES[current_mode]}"
    )

    return "break"


def toggle_always_on_top(event=None):
    global always_on_top

    always_on_top = (
        not always_on_top
    )

    root.attributes(
        "-topmost",
        always_on_top
    )

    print(
        "[Window] Always on top:",
        "ON"
        if always_on_top
        else "OFF"
    )

    return "break"


# ============================================================
# SETTINGS / KEYBINDS
# ============================================================

def _validated_tk_keybinds(bindings, language=None):
    """
    Valida las keybinds y devuelve sus secuencias Tk.
    También evita que dos acciones usen exactamente la misma.
    """
    language = i18n.normalize_language(
        language or current_language
    )

    sequences = {}

    for action, value in bindings.items():
        sequence = config_manager.keybind_to_tk(
            value,
            language
        )

        if sequence in sequences.values():
            other_action = next(
                name
                for name, seq in sequences.items()
                if seq == sequence
            )

            raise ValueError(
                i18n.t(
                    "duplicate_keybind",
                    language,
                    a=other_action,
                    b=action,
                )
            )

        sequences[action] = sequence

    return sequences


def _settings_is_open():
    if _settings_window is None:
        return False

    try:
        return bool(_settings_window.winfo_exists())
    except tk.TclError:
        return False


def _handle_hotkey_action(action):
    """Run one configured shortcut on Tk's main thread."""

    # While Options is open, shortcuts are ignored by the overlay. The
    # low-level hook does not consume the key, so the capture field still
    # receives Tab/1/Ctrl+M normally.
    if _settings_is_open():
        return

    handlers = {
        "toggle_topmost": toggle_always_on_top,
        "cycle_mode": cycle_mode,
        "open_settings": open_settings,
    }

    handler = handlers.get(action)
    if handler is not None:
        handler()


def _poll_global_hotkeys():
    if os.name != "nt":
        return

    for action in hotkey_manager.poll_actions():
        _handle_hotkey_action(action)


def _dispatch_keypress(event):
    """Tk-only fallback used on non-Windows systems."""
    if _settings_is_open():
        return None

    spec = _key_event_to_spec(event)
    if spec is None:
        return None

    try:
        event_sequence = config_manager.keybind_to_tk(
            spec,
            current_language,
        )
        sequences = _validated_tk_keybinds(
            current_keybinds,
            current_language,
        )
    except ValueError:
        return None

    handlers = {
        "toggle_topmost": toggle_always_on_top,
        "cycle_mode": cycle_mode,
        "open_settings": open_settings,
    }

    for action, sequence in sequences.items():
        if sequence == event_sequence:
            return handlers[action](event)

    return None


def apply_keybinds():
    """Validate and apply keybinds without restarting Daniel."""
    global _bound_key_sequences
    global _local_key_dispatch_installed

    sequences = _validated_tk_keybinds(
        current_keybinds,
        current_language,
    )

    _bound_key_sequences = dict(sequences)

    if os.name == "nt":
        # A Windows low-level hook keeps the shortcuts working even while
        # Etterna owns the keyboard focus. The hook never consumes keys.
        hotkey_manager.set_bindings(
            current_keybinds,
            current_language,
        )

        started = hotkey_manager.start()
        if started:
            print("[Keybinds] Global keyboard hook active")
        else:
            print(
                "[Keybinds] Warning: global keyboard hook could not start."
            )

    elif not _local_key_dispatch_installed:
        root.bind_all(
            "<KeyPress>",
            _dispatch_keypress,
            add="+",
        )
        _local_key_dispatch_installed = True

    print("[Keybinds]", current_keybinds)


_MODIFIER_KEYSYMS = {
    "Control_L", "Control_R",
    "Shift_L", "Shift_R",
    "Alt_L", "Alt_R",
    "Meta_L", "Meta_R",
    "Super_L", "Super_R",
    "Caps_Lock", "Num_Lock",
}

_KEYSYM_DISPLAY = {
    "Tab": "Tab",
    "ISO_Left_Tab": "Tab",
    "Escape": "Escape",
    "Return": "Enter",
    "space": "Space",
    "BackSpace": "Backspace",
    "Delete": "Delete",
    "Insert": "Insert",
    "Home": "Home",
    "End": "End",
    "Prior": "PageUp",
    "Next": "PageDown",
    "Up": "Up",
    "Down": "Down",
    "Left": "Left",
    "Right": "Right",
    "plus": "Plus",
    "minus": "Minus",
    "equal": "Equal",
    "comma": "Comma",
    "period": "Period",
    "slash": "Slash",
    "backslash": "Backslash",
    "semicolon": "Semicolon",
    "apostrophe": "Apostrophe",
    "bracketleft": "BracketLeft",
    "bracketright": "BracketRight",
    "grave": "Grave",
}


def _key_event_to_spec(event):
    """
    Convierte un KeyPress real a la notación amigable usada
    por config_manager, por ejemplo Ctrl+Shift+M o Tab.
    """
    keysym = str(event.keysym or "")

    if not keysym or keysym in _MODIFIER_KEYSYMS:
        return None

    modifiers = []

    # En Windows no usamos event.state para detectar modificadores.
    # Tk puede incluir bits internos/extendidos en event.state y en algunas
    # configuraciones eso hacía que cualquier tecla apareciera como Alt+X.
    # GetAsyncKeyState refleja únicamente el estado real del teclado.
    if os.name == "nt" and hasattr(ctypes, "windll"):
        user32 = ctypes.windll.user32

        if user32.GetAsyncKeyState(0x11) & 0x8000:  # VK_CONTROL
            modifiers.append("Ctrl")

        if user32.GetAsyncKeyState(0x10) & 0x8000:  # VK_SHIFT
            modifiers.append("Shift")

        if user32.GetAsyncKeyState(0x12) & 0x8000:  # VK_MENU / Alt
            modifiers.append("Alt")

    else:
        state = int(event.state or 0)

        if state & 0x0004:
            modifiers.append("Ctrl")

        if state & 0x0001:
            modifiers.append("Shift")

        if state & 0x0008:
            modifiers.append("Alt")

    # Shift+Tab puede llegar como ISO_Left_Tab.
    if keysym == "ISO_Left_Tab" and "Shift" not in modifiers:
        modifiers.append("Shift")

    if keysym in _KEYSYM_DISPLAY:
        key = _KEYSYM_DISPLAY[keysym]

    elif (
        keysym.startswith("F")
        and keysym[1:].isdigit()
        and 1 <= int(keysym[1:]) <= 24
    ):
        key = keysym.upper()

    elif len(keysym) == 1:
        key = keysym.upper()

    else:
        # Si Tk entrega un keysym que nuestro parser no conoce,
        # no modificamos el valor actual.
        return None

    return "+".join(modifiers + [key])


def _make_key_capture_entry(
    parent,
    variable,
    x,
    y,
    width,
    height,
    bg,
    fg,
    font,
):
    """
    Campo de keybind de solo lectura.

    No permite escribir ni pegar texto: el valor únicamente
    cambia cuando el usuario presiona una tecla o combinación.
    Tab también se captura en vez de mover el foco.
    """
    entry = tk.Entry(
        parent,
        textvariable=variable,
        state="readonly",
        readonlybackground=bg,
        fg=fg,
        relief="flat",
        font=font,
        takefocus=True,
        cursor="hand2",
    )

    entry.place(
        x=x,
        y=y,
        width=width,
        height=height,
    )

    def _focus(event=None):
        entry.focus_set()
        return "break"

    def _capture(event):
        spec = _key_event_to_spec(event)

        # Las teclas modificadoras solas no se guardan.
        # Se espera a la siguiente tecla para formar Ctrl+X, etc.
        if spec is not None:
            variable.set(spec)

        # Fundamental: detiene el comportamiento normal del Entry,
        # incluyendo la navegación de foco con Tab.
        return "break"

    entry.bind("<Button-1>", _focus)
    entry.bind("<KeyPress>", _capture)
    entry.bind("<<Paste>>", lambda event: "break")
    entry.bind("<<Cut>>", lambda event: "break")

    return entry


def open_settings(event=None):
    """Abre el menú de opciones."""
    global _settings_window

    if _settings_window is not None:
        try:
            if _settings_window.winfo_exists():
                _settings_window.lift()
                _settings_window.focus_force()
                return "break"
        except tk.TclError:
            _settings_window = None

    tr = lambda key, **kwargs: i18n.t(
        key,
        current_language,
        **kwargs
    )

    win = tk.Toplevel(root)
    _settings_window = win

    win.title(tr("settings_window_title"))
    win.geometry("630x560")
    win.resizable(False, False)
    win.configure(bg=BG_COLOR)
    win.transient(root)
    win.lift()

    _set_dark_title_bar(win)

    try:
        win.attributes("-topmost", always_on_top)
    except Exception:
        pass

    title_font = (
        "Segoe UI Semibold",
        _font_size(20)
    )
    normal_font = (
        "Segoe UI",
        _font_size(12)
    )
    small_font = (
        "Segoe UI",
        _font_size(10)
    )

    entry_bg = "#171717"
    button_bg = "#252525"
    fg = "#FFFFFF"
    muted = "#AAAAAA"

    tk.Label(
        win,
        text=tr("settings_heading"),
        bg=BG_COLOR,
        fg=fg,
        font=title_font,
    ).place(x=22, y=18)

    # --------------------------------------------------------
    # IDIOMA
    # --------------------------------------------------------
    tk.Label(
        win,
        text=tr("language"),
        bg=BG_COLOR,
        fg=fg,
        font=normal_font,
    ).place(x=22, y=66)

    language_var = tk.StringVar(
        value=i18n.language_name(current_language)
    )

    language_combo = ttk.Combobox(
        win,
        textvariable=language_var,
        values=list(i18n.SUPPORTED_LANGUAGES.values()),
        state="readonly",
        font=small_font,
    )
    language_combo.place(
        x=205,
        y=64,
        width=180,
        height=28,
    )

    tk.Label(
        win,
        text=tr("language_hint"),
        bg=BG_COLOR,
        fg=muted,
        font=small_font,
    ).place(x=22, y=98)

    # --------------------------------------------------------
    # RUTA ETTERNA
    # --------------------------------------------------------
    tk.Label(
        win,
        text=tr("etterna_path"),
        bg=BG_COLOR,
        fg=fg,
        font=normal_font,
    ).place(x=22, y=132)

    current_path = (
        str(ETTERNA_ROOT)
        if ETTERNA_ROOT is not None
        else ""
    )
    path_var = tk.StringVar(value=current_path)

    path_entry = tk.Entry(
        win,
        textvariable=path_var,
        bg=entry_bg,
        fg=fg,
        insertbackground=fg,
        relief="flat",
        font=small_font,
    )
    path_entry.place(
        x=22,
        y=160,
        width=470,
        height=30,
    )

    def _browse_etterna():
        initial = path_var.get().strip()

        if not initial or not Path(initial).exists():
            initial = str(Path.home())

        selected = filedialog.askdirectory(
            parent=win,
            title=tr("browse_title"),
            initialdir=initial,
        )

        if selected:
            path_var.set(selected)

    tk.Button(
        win,
        text=tr("browse"),
        command=_browse_etterna,
        bg=button_bg,
        fg=fg,
        activebackground="#333333",
        activeforeground=fg,
        relief="flat",
        font=small_font,
    ).place(
        x=502,
        y=160,
        width=105,
        height=30,
    )

    tk.Label(
        win,
        text=tr("path_hint"),
        bg=BG_COLOR,
        fg=muted,
        font=small_font,
    ).place(x=22, y=196)

    # --------------------------------------------------------
    # KEYBINDS
    # --------------------------------------------------------
    tk.Label(
        win,
        text=tr("keybinds"),
        bg=BG_COLOR,
        fg=fg,
        font=normal_font,
    ).place(x=22, y=234)

    tk.Label(
        win,
        text=tr("keybind_hint"),
        bg=BG_COLOR,
        fg=muted,
        font=small_font,
    ).place(x=22, y=260)

    key_vars = {
        action: tk.StringVar(
            value=current_keybinds[action]
        )
        for action in (
            "toggle_topmost",
            "cycle_mode",
            "open_settings",
        )
    }

    rows = [
        (tr("always_on_top"), "toggle_topmost"),
        (tr("cycle_mode"), "cycle_mode"),
        (tr("open_settings"), "open_settings"),
    ]

    y = 294
    key_entries = {}

    for label, action in rows:
        tk.Label(
            win,
            text=label,
            bg=BG_COLOR,
            fg=fg,
            font=small_font,
            anchor="w",
        ).place(
            x=22,
            y=y + 5,
            width=175,
        )

        key_entries[action] = _make_key_capture_entry(
            parent=win,
            variable=key_vars[action],
            x=205,
            y=y,
            width=180,
            height=29,
            bg=entry_bg,
            fg=fg,
            font=small_font,
        )

        y += 38

    def _restore_defaults():
        defaults = config_manager.DEFAULT_CONFIG["keybinds"]
        for action, value in defaults.items():
            key_vars[action].set(value)

    tk.Button(
        win,
        text=tr("restore_keybinds"),
        command=_restore_defaults,
        bg=button_bg,
        fg=fg,
        activebackground="#333333",
        activeforeground=fg,
        relief="flat",
        font=small_font,
    ).place(
        x=405,
        y=294,
        width=180,
        height=29,
    )

    # --------------------------------------------------------
    # CREDITS
    # --------------------------------------------------------
    credits_separator = tk.Frame(
        win,
        bg="#404040",
    )
    credits_separator.place(
        x=22,
        y=414,
        width=585,
        height=1,
    )

    tk.Label(
        win,
        text="Daniel by TheBagelOfMan.",
        bg=BG_COLOR,
        fg="#888888",
        font=("Segoe UI", _font_size(10)),
    ).place(
        x=22,
        y=424,
        width=585,
    )

    tk.Label(
        win,
        text="Port by ChatGPT (and JoseMGS).",
        bg=BG_COLOR,
        fg="#888888",
        font=("Segoe UI", _font_size(10)),
    ).place(
        x=22,
        y=442,
        width=585,
    )

    tk.Label(
        win,
        text="Dan brainrot is spreading",
        bg=BG_COLOR,
        fg="#666666",
        font=("Segoe UI", _font_size(8)),
    ).place(
        x=22,
        y=460,
        width=585,
    )

    config_path_text = str(
        config_manager.get_config_path()
    )

    tk.Label(
        win,
        text=tr(
            "config_path",
            path=config_path_text,
        ),
        bg=BG_COLOR,
        fg="#777777",
        font=("Segoe UI", _font_size(12)),
        anchor="w",
    ).place(
        x=22,
        y=492,
        width=585,
    )

    def _on_close():
        global _settings_window
        _settings_window = None
        win.destroy()

    def _save_settings():
        global APP_CONFIG
        global current_keybinds
        global current_language
        global _settings_window

        proposed_language = i18n.language_code_from_name(
            language_var.get()
        )

        path_value = path_var.get().strip()

        valid_path, path_message = (
            config_manager.validate_etterna_root(
                path_value,
                proposed_language,
            )
        )

        if not valid_path:
            messagebox.showerror(
                i18n.t(
                    "etterna_path_error_title",
                    proposed_language,
                ),
                path_message,
                parent=win,
            )
            return

        proposed = {
            action: key_vars[action].get().strip()
            for action in key_vars
        }

        try:
            _validated_tk_keybinds(
                proposed,
                proposed_language,
            )
        except ValueError as exc:
            messagebox.showerror(
                i18n.t(
                    "keybind_error_title",
                    proposed_language,
                ),
                str(exc),
                parent=win,
            )
            return

        clean_path = str(
            Path(path_value).resolve()
        )

        new_config = {
            "etterna_root": clean_path,
            "language": proposed_language,
            "keybinds": dict(proposed),
        }

        try:
            config_manager.save_config(new_config)
        except OSError as exc:
            messagebox.showerror(
                i18n.t(
                    "save_error_title",
                    proposed_language,
                ),
                str(exc),
                parent=win,
            )
            return

        APP_CONFIG = new_config
        current_language = proposed_language
        current_keybinds = dict(proposed)

        _set_etterna_root(clean_path)
        apply_keybinds()

        if connection_phase != "ready":
            _draw_connection_screen()
        else:
            update_dan_text(
                _last_dan_label,
                _last_dan_numeric,
            )

        print(
            "[Settings] Saved:",
            config_manager.get_config_path(),
        )

        _settings_window = None
        win.destroy()

    tk.Button(
        win,
        text=tr("cancel"),
        command=_on_close,
        bg=button_bg,
        fg=fg,
        activebackground="#333333",
        activeforeground=fg,
        relief="flat",
        font=small_font,
    ).place(
        x=410,
        y=520,
        width=90,
        height=28,
    )

    tk.Button(
        win,
        text=tr("save"),
        command=_save_settings,
        bg="#FFFFFF",
        fg="#000000",
        activebackground="#DDDDDD",
        activeforeground="#000000",
        relief="flat",
        font=small_font,
    ).place(
        x=510,
        y=520,
        width=96,
        height=28,
    )

    win.protocol("WM_DELETE_WINDOW", _on_close)
    win.focus_force()

    return "break"

# El contenido se adapta al tamaño de la ventana.
root.bind(
    "<Configure>",
    _on_window_resize
)

# --- Tick loop ---

def _tick():

    global loading_step
    global _last_loading_dot


    # Global hotkey callbacks are queued by the Windows hook thread and
    # executed here, safely on Tk's main thread.
    _poll_global_hotkeys()

    now = time.monotonic()


    # ========================================================
    # ANIMACION DE CARGA
    # ========================================================

    if (
        loading
        and now - _last_loading_dot >= 0.4
    ):

        dots = [
            ".",
            "..",
            "..."
        ]

        update_dan_text(
            dots[
                loading_step % 3
            ],
            ""
        )

        loading_step += 1

        _last_loading_dot = now


    # ========================================================
    # GRAFICO
    # ========================================================

    if (
        connection_phase == "ready"
        and current_mode == MODE_FULL
    ):

        with lock:

            gp_music = gameplay_music_ms
            gp_recv = gameplay_receive_time
            gp_rate = gameplay_rate
            gp_active = gameplay_active

            mn_music = menu_music_ms
            mn_start = menu_sample_start_ms
            mn_recv = menu_receive_time
            mn_rate = menu_rate


        # ====================================================
        # GAMEPLAY
        # ====================================================

        gameplay_fresh = (
            gp_active
            and gp_recv > 0
            and (now - gp_recv) < 0.40
        )


        if gameplay_fresh:

            position_ms = (
                gp_music / gp_rate
            )


            # Interpolacion entre muestras

            position_ms += (
                (now - gp_recv)
                * 1000.0
            )


            graph.update_position(
                position_ms,
                "NM"
            )


        # ====================================================
        # MENU / PREVIEW
        # ====================================================

        else:

            menu_fresh = (
                mn_recv > 0
                and (now - mn_recv) < 0.40
            )


            if menu_fresh:

                if mn_rate <= 0:
                    mn_rate = 1.0

                # GAMESTATE:GetCurMusicSeconds() entrega la
                # posicion actual de la musica en segundos de
                # la fuente original.
                #
                # Como el chart que recibe Daniel ya fue
                # comprimido por rate (timestamp / rate),
                # la posicion del cursor debe usar exactamente
                # la misma transformacion.
                #
                # No reconstruimos el tiempo a partir de
                # sample_start: usamos directamente el reloj
                # actual de Etterna.

                position_ms = (
                    mn_music / mn_rate
                )


                # Entre escrituras del bridge avanzamos en
                # tiempo real. Despues de dividir por rate,
                # la linea temporal rateada avanza a 1x real.

                position_ms += (
                    (now - mn_recv)
                    * 1000.0
                )


                graph.update_position(
                    position_ms,
                    "NM"
                )


    root.after(
        16,
        _tick
    )

# --- WebSocket callbacks ---

def on_open(ws_app):
    global connection_phase, last_state
    print("[WS] Connected to tosu.")
    last_state = None
    connection_phase = "waiting_map"
    root.after(0, _draw_connection_screen)


def on_message(ws_app, msg):
    global current_map, current_mod, current_song_time_ms
    global _ws_receive_time, _ws_song_time_ms, _prev_song_time_ms, _prev_receive_time
    global connection_phase, last_state, _last_message_time
    global _paused, _pause_time_ms, _frozen_interp_ms

    _last_message_time = time.monotonic()

    try:
        d = json.loads(msg)
        bm = d.get("menu", {}).get("bm")
        if not bm:
            return

        folder = bm["path"]["folder"]
        file = bm["path"]["file"]

        if not folder or not file:
            if connection_phase == "ready":
                print("[WS] osu closed — no map data.")
                last_state = None
                connection_phase = "waiting_map"
                root.after(0, _clear_normal_ui)
                root.after(0, _draw_connection_screen)
            return

        songs = d["settings"]["folders"]["songs"]
        new_map = os.path.join(songs, folder, file)
        new_mod = get_rate_mod(read_mods(d))
        new_time = bm.get("time", {}).get("current", 0)
        now = time.monotonic()

        with lock:
            prev_ws_time = _ws_song_time_ms
            current_map = new_map
            current_mod = new_mod
            current_song_time_ms = new_time
            _prev_song_time_ms = _ws_song_time_ms
            _prev_receive_time = _ws_receive_time
            _ws_song_time_ms = new_time
            _ws_receive_time = now

        sd = current_strain_data
        t_max_ms = float(sd[0][-1]) if (sd is not None and len(sd[0]) > 0) else None
        at_end = (t_max_ms is not None) and (new_time >= t_max_ms - 500)

        time_delta = new_time - prev_ws_time
        jumped = abs(time_delta) > TIME_JUMP_THRESHOLD_MS and not (0 < time_delta < TIME_JUMP_THRESHOLD_MS)

        if jumped and not at_end:
            if _paused:
                _paused = False
                _pause_time_ms = 0
            print(f"[Jump] Time jumped {time_delta:+.0f} ms — clearing pause markers")
            root.after(0, graph.clear_all_pause_markers)

        elif new_time == prev_ws_time and not at_end:
            if not _paused:
                _paused = True
                _pause_time_ms = new_time
                _frozen_interp_ms = float(new_time)
                print(f"[Pause] Detected at {new_time} ms")
                root.after(0, lambda t=new_time, m=new_mod: graph.add_pause_marker(t, m))

        else:
            if _paused:
                _paused = False
                _pause_time_ms = 0
                print(f"[Pause] Resumed at {new_time} ms")

        if connection_phase != "ready":
            connection_phase = "ready"
            print("[WS] Map data received. Entering normal operation.")
            root.after(0, _clear_connection_screen)

    except Exception:
        pass


def on_close(ws_app, close_status_code, close_msg):
    global connection_phase, last_state, _paused
    print(f"[WS] Disconnected from tosu (code={close_status_code}).")
    last_state = None
    _paused = False
    connection_phase = "connecting"
    root.after(0, _clear_normal_ui)
    root.after(0, _draw_connection_screen)


def on_error(ws_app, error):
    print(f"[WS] Error: {error}")


def read_mods(d):
    return (
        d.get("gameplay", {}).get("mods", {}).get("str")
        or d.get("menu", {}).get("mods", {}).get("str")
        or ""
    )


def get_rate_mod(m):
    if "DT" in m or "NC" in m:
        return "DT"
    if "HT" in m:
        return "HT"
    return "NM"

# ============================================================
# ETTERNA BRIDGE
# ============================================================

def _read_bridge_file(path):
    """
    Lee un archivo bridge key=value.
    Acepta path=None para permitir que el programa arranque
    antes de que el usuario configure la ruta de Etterna.
    """
    if (
        path is None
        or not path.exists()
    ):
        return None

    try:
        text = path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

    except OSError:
        return None

    data = {}

    for line in text.splitlines():

        if "=" not in line:
            continue

        key, value = line.split(
            "=",
            1
        )

        data[
            key.strip()
        ] = value.strip()

    return data


def read_etterna_bridge():
    return _read_bridge_file(
        BRIDGE_FILE
    )


def read_gameplay_bridge():
    return _read_bridge_file(
        GAMEPLAY_FILE
    )


def read_menu_bridge():
    return _read_bridge_file(
        MENU_FILE
    )


def etterna_menu_loop():

    global menu_music_ms
    global menu_sample_start_ms
    global menu_receive_time
    global menu_rate

    last_mtime = None
    last_source = None

    while True:

        menu_file = MENU_FILE

        if (
            menu_file is None
            or not menu_file.exists()
        ):
            last_mtime = None
            last_source = None
            time.sleep(0.05)
            continue

        source = str(
            menu_file
        )

        if source != last_source:
            last_source = source
            last_mtime = None

        try:
            mtime = (
                menu_file
                .stat()
                .st_mtime_ns
            )

        except OSError:
            time.sleep(0.05)
            continue

        if mtime == last_mtime:
            time.sleep(0.03)
            continue

        last_mtime = mtime

        state = _read_bridge_file(
            menu_file
        )

        if not state:
            time.sleep(0.03)
            continue

        try:
            music_ms = (
                float(
                    state.get(
                        "music_seconds",
                        "0"
                    )
                )
                * 1000.0
            )

        except ValueError:
            music_ms = 0.0

        try:
            sample_start_ms = (
                float(
                    state.get(
                        "sample_start",
                        "0"
                    )
                )
                * 1000.0
            )

        except ValueError:
            sample_start_ms = 0.0

        try:
            rate = float(
                state.get(
                    "rate",
                    "1"
                )
            )

        except ValueError:
            rate = 1.0

        if rate <= 0:
            rate = 1.0

        with lock:

            menu_music_ms = music_ms

            menu_sample_start_ms = (
                sample_start_ms
            )

            menu_rate = rate

            menu_receive_time = (
                time.monotonic()
            )

        time.sleep(0.03)


def etterna_gameplay_loop():

    global gameplay_music_ms
    global gameplay_receive_time
    global gameplay_rate
    global gameplay_active

    last_mtime = None
    last_source = None

    while True:

        gameplay_file = GAMEPLAY_FILE

        if (
            gameplay_file is None
            or not gameplay_file.exists()
        ):
            last_mtime = None
            last_source = None
            time.sleep(0.05)
            continue

        source = str(
            gameplay_file
        )

        if source != last_source:
            last_source = source
            last_mtime = None

        try:
            mtime = (
                gameplay_file
                .stat()
                .st_mtime_ns
            )

        except OSError:
            time.sleep(0.05)
            continue

        if mtime == last_mtime:
            time.sleep(0.03)
            continue

        last_mtime = mtime

        state = _read_bridge_file(
            gameplay_file
        )

        if not state:
            time.sleep(0.03)
            continue

        try:
            music_ms = (
                float(
                    state.get(
                        "music_seconds",
                        "0"
                    )
                )
                * 1000.0
            )

        except ValueError:
            music_ms = 0.0

        try:
            rate = float(
                state.get(
                    "rate",
                    "1"
                )
            )

        except ValueError:
            rate = 1.0

        if rate <= 0:
            rate = 1.0

        playing = (
            state.get(
                "playing",
                "0"
            )
            == "1"
        )

        with lock:

            gameplay_music_ms = music_ms
            gameplay_rate = rate
            gameplay_active = playing

            gameplay_receive_time = (
                time.monotonic()
            )

        time.sleep(0.03)


def normalize_difficulty(value):

    if not value:
        return ""

    value = value.strip()

    value = value.replace(
        "Difficulty_",
        ""
    )

    return value.lower()


def resolve_song_directory(song_dir):

    if (
        not song_dir
        or ETTERNA_ROOT is None
    ):
        return None

    parts = [
        part
        for part in song_dir
        .replace("\\", "/")
        .split("/")
        if part
    ]

    path = ETTERNA_ROOT

    for part in parts:
        path = path / part

    return path
    
def resolve_step_file(step_file):

    if not step_file:
        return None

    raw = (
        step_file
        .strip()
        .replace("\\", "/")
    )

    # Primero probamos exactamente
    # lo que nos dio Etterna.
    direct = Path(raw)

    if (
        direct.is_absolute()
        and direct.exists()
    ):
        return direct

    if ETTERNA_ROOT is None:
        return None

    # Puede venir como:
    #
    # Songs/Pack/Cancion/chart.osu
    #
    # o:
    #
    # /Songs/Pack/Cancion/chart.sm

    parts = [
        part
        for part in raw.split("/")
        if part
    ]

    candidate = ETTERNA_ROOT

    for part in parts:
        candidate = candidate / part

    return candidate


def find_sm_file(song_directory):

    if (
        song_directory is None
        or not song_directory.exists()
    ):
        return None

    files = list(
        song_directory.glob("*.sm")
    )

    if not files:
        return None

    return files[0]


def find_selected_sm_chart(
    data,
    difficulty,
    meter,
    description=""
):

    target_diff = (
        normalize_difficulty(
            difficulty
        )
    )


    target_description = (
        description
        or ""
    ).strip().lower()


    try:

        target_meter = int(
            float(meter)
        )

    except Exception:

        target_meter = None


    matches = []


    for chart in data["charts"]:

        if (
            chart["stepstype"]
            .strip()
            .lower()
            != "dance-single"
        ):
            continue


        chart_diff = (
            chart["difficulty"]
            .strip()
            .lower()
        )


        try:

            chart_meter = int(
                float(
                    chart["meter"]
                )
            )

        except Exception:

            chart_meter = None


        if chart_diff != target_diff:
            continue


        if (
            target_meter is not None
            and chart_meter
            != target_meter
        ):
            continue


        matches.append(chart)


    # Si Description existe,
    # úsala para desambiguar.
    if (
        len(matches) > 1
        and target_description
    ):

        description_matches = [

            chart

            for chart in matches

            if (
                chart.get(
                    "description",
                    ""
                )
                .strip()
                .lower()
                == target_description
            )

        ]


        if len(description_matches) == 1:

            return description_matches[0]


    if len(matches) == 1:

        return matches[0]


    return None


def apply_etterna_rate(
    notes,
    rate
):

    if rate <= 0:
        rate = 1.0

    return [
        (
            column,
            time_ms / rate
        )
        for column, time_ms in notes
    ]


def get_native_msd_from_state(state):
    """
    Lee los skillsets MSD que Etterna escribió en DanielBridge.txt.
    Devuelve el mismo formato de diccionario que la UI de Daniel espera.
    """

    keys = {
        "overall": "msd_overall",
        "stream": "msd_stream",
        "jumpstream": "msd_jumpstream",
        "handstream": "msd_handstream",
        "stamina": "msd_stamina",
        "jackspeed": "msd_jackspeed",
        "chordjack": "msd_chordjack",
        "technical": "msd_technical",
    }

    result = {}

    for name, bridge_key in keys.items():
        try:
            value = float(
                state.get(
                    bridge_key,
                    "0"
                )
            )
        except (TypeError, ValueError):
            value = 0.0

        result[name] = value

    if result["overall"] <= 0:
        return None

    return result


def etterna_bridge_loop():

    global current_map
    global current_difficulty
    global current_meter
    global current_description
    global current_rate
    global current_native_msd

    global connection_phase
    global last_state


    previous_bridge_state = None


    print(
        "[Etterna] Waiting for bridge..."
    )


    while True:

        state = read_etterna_bridge()


        if not state:

            valid_root = False

            if ETTERNA_ROOT is not None:

                valid_root, _ = (
                    config_manager
                    .validate_etterna_root(
                        ETTERNA_ROOT
                    )
                )

            new_phase = (
                "connecting"
                if valid_root
                else "needs_config"
            )

            phase_changed = (
                connection_phase
                != new_phase
            )

            connection_phase = (
                new_phase
            )

            with lock:
                current_native_msd = None

            if phase_changed:
                root.after(
                    0,
                    _clear_normal_ui
                )

                root.after(
                    0,
                    _draw_connection_screen
                )

            time.sleep(0.2)

            continue


        key = (

            bridge_config_revision,

            state.get(
                "step_file",
                ""
            ),

            state.get(
                "difficulty",
                ""
            ),

            state.get(
                "meter",
                ""
            ),

            state.get(
                "description",
                ""
            ),

            state.get(
                "rate",
                ""
            ),

            state.get(
                "msd_overall",
                ""
            ),

            state.get(
                "msd_stream",
                ""
            ),

            state.get(
                "msd_jumpstream",
                ""
            ),

            state.get(
                "msd_handstream",
                ""
            ),

            state.get(
                "msd_stamina",
                ""
            ),

            state.get(
                "msd_jackspeed",
                ""
            ),

            state.get(
                "msd_chordjack",
                ""
            ),

            state.get(
                "msd_technical",
                ""
            ),

        )


        if key == previous_bridge_state:

            time.sleep(0.1)

            continue


        previous_bridge_state = key


        step_file_raw = state.get(
            "step_file",
            ""
        )


        step_file = resolve_step_file(
            step_file_raw
        )


        if (
            step_file is None
            or not step_file.exists()
        ):

            print()
            print(
                "[Etterna] Step file not found:"
            )

            print(
                step_file_raw
            )

            print(
                "Resolved as:"
            )

            print(
                step_file
            )


            current_map = None

            with lock:
                current_native_msd = None

            connection_phase = (
                "waiting_map"
            )


            root.after(
                0,
                _draw_connection_screen
            )


            time.sleep(0.1)

            continue


        extension = (
            step_file
            .suffix
            .lower()
        )


        if extension not in (
            ".sm",
            ".ssc",
            ".osu"
        ):

            print()
            print(
                "[Etterna] Unsupported format:",
                extension
            )

            current_map = None

            with lock:
                current_native_msd = None

            connection_phase = (
                "waiting_map"
            )

            root.after(
                0,
                _draw_connection_screen
            )

            time.sleep(0.1)

            continue


        try:

            rate = float(
                state.get(
                    "rate",
                    "1"
                )
            )

        except ValueError:

            rate = 1.0


        native_msd = get_native_msd_from_state(
            state
        )


        with lock:

            current_map = str(
                step_file
            )

            current_difficulty = (
                state.get(
                    "difficulty",
                    ""
                )
            )

            current_meter = (
                state.get(
                    "meter",
                    ""
                )
            )

            current_description = (
                state.get(
                    "description",
                    ""
                )
            )

            current_rate = rate

            current_native_msd = native_msd


        # Forzar nuevo cálculo.
        last_state = None


        if connection_phase != "ready":

            connection_phase = "ready"

            root.after(
                0,
                _clear_connection_screen
            )


        print()
        print(
            "[Etterna] Chart changed"
        )

        print(
            "File:",
            step_file
        )

        print(
            "Format:",
            extension
        )

        print(
            "Difficulty:",
            current_difficulty
        )

        print(
            "Meter:",
            current_meter
        )

        print(
            "Description:",
            current_description
        )

        print(
            "Rate:",
            current_rate
        )


        time.sleep(0.1)

# --- Calculation loop ---

def calculation_loop():

    global last_state
    global loading
    global loading_step

    global current_strain_data
    global current_msd_data
    global current_native_msd

    global _last_dan_label
    global _last_dan_numeric

    while True:

        if connection_phase != "ready":

            time.sleep(0.1)
            continue


        with lock:

            state = (
                current_map,
                current_difficulty,
                current_meter,
                current_description,
                current_rate
            )


        (
            mp,
            difficulty,
            meter,
            description,
            rate
        ) = state


        if (
            not mp
            or not os.path.exists(mp)
        ):

            time.sleep(0.1)
            continue


        if state == last_state:

            time.sleep(0.1)
            continue


        try:

            loading = True
            loading_step = 0


            # =================================================
            # CARGAR ARCHIVO SELECCIONADO
            # =================================================

            data = (
                chart_loader
                .load_chart_file(mp)
            )


            extension = (
                Path(mp)
                .suffix
                .lower()
            )


            # =================================================
            # .SM / .SSC
            # =================================================

            if extension in (
                ".sm",
                ".ssc"
            ):

                selected = (
                    find_selected_sm_chart(
                        data,
                        difficulty,
                        meter,
                        description
                    )
                )


                if selected is None:

                    raise ValueError(
                        "Could not uniquely identify "
                        "selected StepMania chart"
                    )


                print()
                print(
                    "[Etterna Chart - "
                    + extension[1:].upper()
                    + "]"
                )

                print(
                    "File:",
                    os.path.basename(mp)
                )

                print(
                    "Difficulty:",
                    selected["difficulty"]
                )

                print(
                    "Meter:",
                    selected["meter"]
                )

                print(
                    "Description:",
                    selected["description"]
                )

                print(
                    "Rate:",
                    rate
                )


                notes, ignored = (
                    chart_loader
                    .convert_stepmania_chart(
                        data,
                        selected
                    )
                )


                # Daniel originalmente necesita
                # un OD para algunas fórmulas.
                #
                # .sm/.ssc no poseen OverallDifficulty
                # equivalente al de osu!, así que
                # mantenemos el valor que ya usábamos.
                od = 9


            # =================================================
            # .OSU
            # =================================================

            elif extension == ".osu":

                print()
                print(
                    "[Etterna Chart - OSU]"
                )

                print(
                    "File:",
                    os.path.basename(mp)
                )

                print(
                    "Difficulty:",
                    difficulty
                )

                print(
                    "Meter:",
                    meter
                )

                print(
                    "Description:",
                    description
                )

                print(
                    "Rate:",
                    rate
                )


                if data["format"] != "osu":

                    raise ValueError(
                        "chart_loader did not "
                        "recognize the .osu file"
                    )


                if data["keycount"] != 4:

                    raise ValueError(
                        "Daniel only supports 4K"
                    )


                notes = data["notes"]

                ignored = {}


                # Aquí sí conservamos el OD
                # original del .osu.
                od = data["od"]


            # =================================================
            # OTRO FORMATO
            # =================================================

            else:

                raise ValueError(
                    "Unsupported chart format: "
                    + extension
                )


            if not notes:

                raise ValueError(
                    "Chart contains no playable notes"
                )


            # =================================================
            # APLICAR RATE
            # =================================================

            rated_notes = (
                apply_etterna_rate(
                    notes,
                    rate
                )
            )


            # =================================================
            # DANIEL / SUNNY
            # =================================================

            (
                SR,
                times,
                strain,
                factors
            ) = algorithm.calculate_notes(
                notes=rated_notes,
                keycount=4,
                mod="NM",
                od=od
            )


            t_arr = np.asarray(
                times,
                dtype=float
            )

            d_arr = np.asarray(
                strain,
                dtype=float
            )


            current_strain_data = (
                t_arr,
                d_arr
            )


            # =================================================
            # MSD NATIVO DE ETTERNA
            # =================================================

            with lock:

                if current_native_msd is not None:

                    msd_result = (
                        current_native_msd.copy()
                    )

                else:

                    msd_result = None


            print()
            print(
                "[Etterna Native MSD]"
            )


            if msd_result is not None:

                for k, v in (
                    msd_result.items()
                ):

                    print(
                        f"{k:<10}: {v:.2f}"
                    )

            else:

                print(
                    "MSD unavailable"
                )


            with lock:

                current_msd_data = (
                    msd_result
                )


            # =================================================
            # FACTORES + DAN
            # =================================================

            averages = (
                algorithm.factor_averages(
                    times,
                    factors
                )
            )


            dan_label, dan_numeric = (
                get_dan_from_diff(
                    SR
                )
            )


            _last_dan_label = (
                dan_label
            )

            _last_dan_numeric = (
                dan_numeric
            )


            print()
            print(
                "[Map Factors]"
            )

            for k, v in averages.items():

                print(
                    f"{k:<6}: {v:.4f}"
                )


            print(
                f"SR    : {SR:.4f}★"
            )

            print(
                "Dan   : "
                f"{dan_label} "
                f"({dan_numeric})"
            )

            print()


            # =================================================
            # ACTUALIZAR OVERLAY
            # =================================================

            loading = False
            last_state = state


            if current_mode == MODE_FULL:

                root.after(
                    0,
                    lambda _t=t_arr,
                    _d=d_arr:
                    graph.set_data(
                        _t,
                        _d
                    )
                )

                root.after(
                    0,
                    lambda:
                    graph.set_color(
                        current_bar_color
                    )
                )

                root.after(
                    0,
                    graph.show
                )


            set_dan_text(
                dan_label,
                dan_numeric
            )


        except Exception as e:

            loading = False
            last_state = state

            print(
                "Calculation error:",
                e
            )


            _last_dan_label = (
                "Invalid Beatmap"
            )

            _last_dan_numeric = ""


            with lock:

                current_msd_data = None
                current_strain_data = None


            root.after(
                0,
                _clear_invalid_ui
            )

            set_dan_text(
                "Invalid Beatmap",
                ""
            )


        time.sleep(0.1)


# --- Dan boundary tables ---

def _precompute_dan_boundaries():
    means = [DAN_MEANS[d] for d in ORDER]
    boundaries = []
    for i in range(len(ORDER)):
        mean = means[i]
        lower = (means[i - 1] + mean) / 2 if i > 0 else mean - ((means[1] + mean) / 2 - mean)
        upper = (mean + means[i + 1]) / 2 if i < len(means) - 1 else mean + (mean - means[i - 1]) / 2
        boundaries.append((lower, upper))
    return boundaries


_DAN_BOUNDARIES = _precompute_dan_boundaries()


def get_dan_from_diff(diff):

    # ========================================================
    # DANS NUMERICOS POR DEBAJO DE ALPHA
    # ========================================================

    if diff < _DAN_BOUNDARIES[0][0]:

        lower, upper = _DAN_BOUNDARIES[0]

        alpha_width = (
            upper - lower
        )


        # Extrapolamos hacia abajo usando
        # el mismo ancho que el rango Alpha.
        numeric_raw = (
            DAN_ORDER_START
            + (diff - lower)
            / alpha_width
        )


        # Por debajo de 1st Dan
        if numeric_raw < 1.0:

            numeric = round(
                max(0.0, numeric_raw),
                2
            )

            return "<1st", numeric


        # Ej:
        #
        # 10.24 -> 10th Dan
        #  8.72 -> 8th Dan
        #
        dan_number = int(
            numeric_raw
        )


        # Seguridad:
        # este bloque solamente debe cubrir
        # 1st-10th.
        dan_number = max(
            1,
            min(10, dan_number)
        )


        # Posicion dentro del Dan:
        #
        # 10.00 - 10.33 = Low
        # 10.33 - 10.66 = Mid
        # 10.66 - 11.00 = High

        tier_position = (
            numeric_raw - dan_number
        )


        if tier_position < 1 / 3:

            tier = "Low"

        elif tier_position < 2 / 3:

            tier = "Mid"

        else:

            tier = "High"


        # Sufijo correcto en ingles.
        if dan_number == 1:
            name = "1st"

        elif dan_number == 2:
            name = "2nd"

        elif dan_number == 3:
            name = "3rd"

        else:
            name = f"{dan_number}th"


        numeric = round(
            numeric_raw,
            2
        )


        return (
            f"{tier}-{name}",
            numeric
        )


    # ========================================================
    # ALPHA EN ADELANTE
    # ========================================================

    if diff >= _DAN_BOUNDARIES[-1][1]:
        return "? ? ? ? ?", "N/A"

    for i, dan in enumerate(ORDER):

        lower, upper = (
            _DAN_BOUNDARIES[i]
        )

        if lower <= diff < upper:

            t = max(
                0.0,
                min(
                    (diff - lower)
                    / (upper - lower),
                    1.0
                )
            )

            numeric = round(
                DAN_ORDER_START
                + i
                + t,
                2
            )

            if t < 1 / 3:
                label = f"Low-{dan}"

            elif t < 2 / 3:
                label = f"Mid-{dan}"

            else:
                label = f"High-{dan}"

            return (
                label,
                numeric
            )


    return "? ? ? ? ?", "N/A"


# --- Boot ---


def _on_app_close():
    try:
        hotkey_manager.stop()
    except Exception:
        pass
    root.destroy()


root.protocol(
    "WM_DELETE_WINDOW",
    _on_app_close
)


# Aplicar keybinds guardadas. Si el archivo de configuración
# contiene una combinación inválida, volver a los defaults.
try:
    apply_keybinds()

except ValueError as exc:

    print(
        "[Keybinds] Invalid config, using defaults:",
        exc
    )

    current_keybinds = dict(
        config_manager
        .DEFAULT_CONFIG[
            "keybinds"
        ]
    )

    APP_CONFIG["keybinds"] = dict(
        current_keybinds
    )

    apply_keybinds()


root.after(
    100,
    _draw_connection_screen
)


# Si es la primera ejecución (o la ruta ya no existe),
# abrir automáticamente Opciones.
_initial_path_valid = False

if ETTERNA_ROOT is not None:

    _initial_path_valid, _ = (
        config_manager
        .validate_etterna_root(
            ETTERNA_ROOT,
            current_language
        )
    )

if not _initial_path_valid:

    root.after(
        350,
        open_settings
    )


def _ws_loop():
    return


def _message_timeout_watcher():
    return


threading.Thread(
    target=calculation_loop,
    daemon=True
).start()

threading.Thread(
    target=etterna_bridge_loop,
    daemon=True
).start()

threading.Thread(
    target=etterna_gameplay_loop,
    daemon=True
).start()

threading.Thread(
    target=etterna_menu_loop,
    daemon=True
).start()

root.after(
    16,
    _tick
)

root.mainloop()

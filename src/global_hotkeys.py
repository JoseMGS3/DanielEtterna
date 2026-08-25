import os
import queue
import threading
import ctypes
from ctypes import wintypes

import config_manager


# Windows low-level keyboard hook. Unlike Tkinter bindings, this keeps
# working while Etterna (or any other window) has focus.
WH_KEYBOARD_LL = 13
HC_ACTION = 0

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt

VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU = 0xA4
VK_RMENU = 0xA5

_MODIFIER_VKS = {
    VK_SHIFT, VK_CONTROL, VK_MENU,
    VK_LSHIFT, VK_RSHIFT,
    VK_LCONTROL, VK_RCONTROL,
    VK_LMENU, VK_RMENU,
}

_SPECIAL_VKS = {
    "Tab": 0x09,
    "Escape": 0x1B,
    "space": 0x20,
    "Return": 0x0D,
    "BackSpace": 0x08,
    "Delete": 0x2E,
    "Insert": 0x2D,
    "Home": 0x24,
    "End": 0x23,
    "Prior": 0x21,   # PageUp
    "Next": 0x22,    # PageDown
    "Up": 0x26,
    "Down": 0x28,
    "Left": 0x25,
    "Right": 0x27,
    "plus": 0xBB,          # VK_OEM_PLUS
    "equal": 0xBB,
    "minus": 0xBD,         # VK_OEM_MINUS
    "comma": 0xBC,
    "period": 0xBE,
    "slash": 0xBF,
    "backslash": 0xDC,
    "semicolon": 0xBA,
    "apostrophe": 0xDE,
    "bracketleft": 0xDB,
    "bracketright": 0xDD,
    "grave": 0xC0,
}


def _vk_for_tk_key(key):
    if key in _SPECIAL_VKS:
        return _SPECIAL_VKS[key]

    if key.startswith("F") and key[1:].isdigit():
        number = int(key[1:])
        if 1 <= number <= 24:
            return 0x70 + number - 1

    if len(key) == 1:
        ch = key.upper()
        if "A" <= ch <= "Z" or "0" <= ch <= "9":
            return ord(ch)

    raise ValueError(f"Unsupported Windows hotkey key: {key}")


def parse_hotkey(spec, language="en"):
    """Return (frozenset(modifiers), virtual_key) for a friendly keybind."""
    sequence = config_manager.keybind_to_tk(spec, language)
    body = sequence[1:-1]
    parts = body.split("-")

    modifiers = set()
    key = None

    for part in parts:
        if part == "Control":
            modifiers.add("ctrl")
        elif part == "Shift":
            modifiers.add("shift")
        elif part == "Alt":
            modifiers.add("alt")
        else:
            key = part

    if key is None:
        raise ValueError(f"Invalid hotkey: {spec}")

    return frozenset(modifiers), _vk_for_tk_key(key)


if os.name == "nt":
    ULONG_PTR = wintypes.WPARAM

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("vkCode", wintypes.DWORD),
            ("scanCode", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    # Pointer-sized types are important on 64-bit Windows. Using c_long
    # for HHOOK/LRESULT can truncate the hook handle.
    LRESULT = ctypes.c_ssize_t
    WPARAM = ctypes.c_size_t
    LPARAM = ctypes.c_ssize_t
    HHOOK = ctypes.c_void_p
    HINSTANCE = ctypes.c_void_p
    HWND = ctypes.c_void_p

    HOOKPROC = ctypes.WINFUNCTYPE(
        LRESULT,
        ctypes.c_int,
        WPARAM,
        LPARAM,
    )


class GlobalHotkeyManager:
    """
    Non-blocking global hotkeys for Windows.

    The hook never consumes keyboard input: it always calls CallNextHookEx,
    so Etterna continues receiving the same keys. Matched actions are queued
    and must be polled from Tk's main thread with poll_actions().
    """

    def __init__(self):
        self._bindings = {}
        self._bindings_lock = threading.Lock()
        self._actions = queue.Queue()
        self._pressed = set()

        self._thread = None
        self._thread_id = None
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._hook = None
        self._hook_proc = None
        self._start_error = None

    @property
    def supported(self):
        return os.name == "nt"

    def set_bindings(self, bindings, language="en"):
        parsed = {}
        for action, spec in bindings.items():
            parsed[action] = parse_hotkey(spec, language)

        with self._bindings_lock:
            self._bindings = parsed

    def start(self):
        if not self.supported:
            return False

        if self._thread is not None and self._thread.is_alive():
            return True

        self._stop_event.clear()
        self._ready_event.clear()
        self._start_error = None

        self._thread = threading.Thread(
            target=self._hook_loop,
            name="DanielGlobalHotkeys",
            daemon=True,
        )
        self._thread.start()
        self._ready_event.wait(timeout=1.5)

        if self._start_error:
            print("[Keybinds] Global hook error:", self._start_error)
            return False

        return bool(self._thread and self._thread.is_alive())

    def stop(self):
        if not self.supported:
            return

        self._stop_event.set()

        thread_id = self._thread_id
        if thread_id:
            try:
                ctypes.windll.user32.PostThreadMessageW(
                    thread_id,
                    WM_QUIT,
                    0,
                    0,
                )
            except Exception:
                pass

        thread = self._thread
        if thread and thread.is_alive() and threading.current_thread() is not thread:
            thread.join(timeout=1.0)

        self._thread = None
        self._thread_id = None

    def poll_actions(self, limit=20):
        result = []
        for _ in range(limit):
            try:
                result.append(self._actions.get_nowait())
            except queue.Empty:
                break
        return result

    def _current_modifiers(self):
        # Derive modifier state from the low-level hook's own pressed-key set.
        # This is more deterministic than GetAsyncKeyState and avoids stale or
        # phantom Alt states on some Windows/Tk configurations.
        modifiers = set()

        if (
            VK_CONTROL in self._pressed
            or VK_LCONTROL in self._pressed
            or VK_RCONTROL in self._pressed
        ):
            modifiers.add("ctrl")

        if (
            VK_SHIFT in self._pressed
            or VK_LSHIFT in self._pressed
            or VK_RSHIFT in self._pressed
        ):
            modifiers.add("shift")

        if (
            VK_MENU in self._pressed
            or VK_LMENU in self._pressed
            or VK_RMENU in self._pressed
        ):
            modifiers.add("alt")

        return frozenset(modifiers)

    def _match(self, vk_code):
        combo = (self._current_modifiers(), int(vk_code))

        with self._bindings_lock:
            bindings = dict(self._bindings)

        for action, expected in bindings.items():
            if expected == combo:
                self._actions.put(action)
                return

    def _hook_loop(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # Explicit WinAPI signatures are required on 64-bit Python.
        user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int,
            HOOKPROC,
            HINSTANCE,
            wintypes.DWORD,
        ]
        user32.SetWindowsHookExW.restype = HHOOK

        user32.CallNextHookEx.argtypes = [
            HHOOK,
            ctypes.c_int,
            WPARAM,
            LPARAM,
        ]
        user32.CallNextHookEx.restype = LRESULT

        user32.UnhookWindowsHookEx.argtypes = [HHOOK]
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL

        user32.GetMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG),
            HWND,
            wintypes.UINT,
            wintypes.UINT,
        ]
        user32.GetMessageW.restype = wintypes.BOOL

        user32.PeekMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG),
            HWND,
            wintypes.UINT,
            wintypes.UINT,
            wintypes.UINT,
        ]
        user32.PeekMessageW.restype = wintypes.BOOL

        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = HINSTANCE
        kernel32.GetCurrentThreadId.restype = wintypes.DWORD

        self._thread_id = kernel32.GetCurrentThreadId()

        # Force creation of a message queue so PostThreadMessage can stop us.
        msg = wintypes.MSG()
        PM_NOREMOVE = 0x0000
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_NOREMOVE)

        @HOOKPROC
        def hook_proc(n_code, w_param, l_param):
            if n_code == HC_ACTION:
                data = ctypes.cast(
                    l_param,
                    ctypes.POINTER(KBDLLHOOKSTRUCT),
                ).contents

                vk = int(data.vkCode)
                message = int(w_param)

                if message in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    # Track modifiers as real pressed keys so a later keydown
                    # can form Ctrl+X / Shift+X / Alt+X reliably.
                    if vk in _MODIFIER_VKS:
                        self._pressed.add(vk)

                    elif vk not in self._pressed:
                        # Match before adding the ordinary key; only modifier
                        # keys should contribute to the combination.
                        self._match(vk)
                        self._pressed.add(vk)

                elif message in (WM_KEYUP, WM_SYSKEYUP):
                    self._pressed.discard(vk)

            return user32.CallNextHookEx(
                self._hook,
                n_code,
                w_param,
                l_param,
            )

        self._hook_proc = hook_proc

        module_handle = kernel32.GetModuleHandleW(None)
        self._hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self._hook_proc,
            module_handle,
            0,
        )

        if not self._hook:
            self._start_error = ctypes.WinError()
            self._ready_event.set()
            return

        self._ready_event.set()

        try:
            while not self._stop_event.is_set():
                result = user32.GetMessageW(
                    ctypes.byref(msg),
                    None,
                    0,
                    0,
                )

                if result <= 0:
                    break

                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        finally:
            if self._hook:
                try:
                    user32.UnhookWindowsHookEx(self._hook)
                except Exception:
                    pass

            self._hook = None
            self._hook_proc = None
            self._pressed.clear()

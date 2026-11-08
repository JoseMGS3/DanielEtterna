"""Regression tests for focus-only Tab keybinds in DanielEtterna.

The real Tk window is not started: only the local key dispatcher
and registration functions are executed with lightweight fakes.
"""
import ast
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

SOURCE_PATH = Path(__file__).resolve().parents[1] / "src" / "daniel_etterna.py"


def _load_dispatcher_functions(namespace):
    syntax = ast.parse(SOURCE_PATH.read_text(encoding="utf-8"))
    names = {"_dispatch_keypress", "apply_keybinds"}
    functions = [
        node for node in syntax.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    if len(functions) != len(names):
        raise AssertionError("Missing a local keybind function")
    module = ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[]))
    exec(compile(module, str(SOURCE_PATH), "exec"), namespace)


class FakeRoot:
    def __init__(self):
        self.bindings = {}
        self.all_bindings = {}

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = callback

    def bind_all(self, sequence, callback, add=None):
        self.all_bindings[sequence] = callback


class FocusOnlyTabTests(unittest.TestCase):
    def setUp(self):
        self.root = FakeRoot()
        self.actions = []
        self.settings_open = False

        class FakeGlobalManager:
            def stop(self):
                pass

        class FakeConfig:
            @staticmethod
            def keybind_to_tk(spec, language):
                return "<Tab>" if spec == "Tab" else "<x>"

        self.ns = {
            "root": self.root,
            "_validated_tk_keybinds": lambda bindings, language: {
                "cycle_mode": "<Tab>",
            },
            "current_keybinds": {"cycle_mode": "Tab"},
            "current_language": "en",
            "_local_key_dispatch_installed": False,
            "_global_hotkeys_active": False,
            "hotkey_manager": FakeGlobalManager(),
            "current_global_hotkeys": False,
            "os": SimpleNamespace(name="posix"),
            "_settings_is_open": lambda: self.settings_open,
            "_key_event_to_spec": lambda event: event.keysym,
            "config_manager": FakeConfig(),
            "toggle_always_on_top": lambda event: None,
            "cycle_mode": lambda event: self.actions.append("cycle_mode") or "break",
            "open_settings": lambda event: None,
        }
        _load_dispatcher_functions(self.ns)
        self.ns["apply_keybinds"]()

    def test_registers_tab_before_tks_all_focus_traversal(self):
        self.assertIn("<KeyPress>", self.root.all_bindings)
        self.assertIn("<Tab>", self.root.bindings)
        self.assertIn("<Shift-Tab>", self.root.bindings)
        self.assertIn("<ISO_Left_Tab>", self.root.bindings)

    def test_tab_activates_layout_change_without_global_hook(self):
        result = self.root.bindings["<Tab>"](SimpleNamespace(keysym="Tab"))
        self.assertEqual(result, "break")
        self.assertEqual(self.actions, ["cycle_mode"])

    def test_tab_is_not_consumed_while_options_open(self):
        self.settings_open = True
        result = self.root.bindings["<Tab>"](SimpleNamespace(keysym="Tab"))
        self.assertIsNone(result)
        self.assertEqual(self.actions, [])

    def test_local_action_is_not_duplicated_if_global_hook_active(self):
        self.ns["_global_hotkeys_active"] = True
        result = self.root.bindings["<Tab>"](SimpleNamespace(keysym="Tab"))
        self.assertIsNone(result)
        self.assertEqual(self.actions, [])

    def test_nonmatching_key_is_not_consumed(self):
        result = self.root.all_bindings["<KeyPress>"](
            SimpleNamespace(keysym="A")
        )
        self.assertIsNone(result)
        self.assertEqual(self.actions, [])


if __name__ == "__main__":
    unittest.main()

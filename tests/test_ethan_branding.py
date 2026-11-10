"""Ethan branding checks without altering legacy Etterna integration paths."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import i18n


class EthanBrandingTests(unittest.TestCase):
    def test_application_and_settings_windows_are_named_ethan(self):
        source = (ROOT / "src" / "daniel_etterna.py").read_text(
            encoding="utf-8",
        )
        self.assertIn('root.title("Ethan")', source)
        self.assertNotIn('root.title(f"DanielEtterna', source)
        self.assertEqual(i18n.t("settings_window_title", "en"), "Ethan - Settings")
        self.assertEqual(i18n.t("settings_window_title", "es"), "Ethan - Opciones")

    def test_windows_build_outputs_ethan_and_debug_variant(self):
        source = (ROOT / "build_windows.bat").read_text(encoding="utf-8")
        self.assertIn('set "APP_BINARY_NAME=Ethan"', source)
        self.assertIn('set "APP_BINARY_NAME=Ethan-Debug"', source)
        self.assertIn('src\\daniel_etterna.py', source)
        self.assertIn('src\\xdc1.exe', source)

    def test_legacy_config_and_bridge_names_remain_compatible(self):
        source = (ROOT / "src" / "config_manager.py").read_text(
            encoding="utf-8",
        )
        self.assertIn('return Path(base) / "DanielEtterna"', source)
        self.assertIn('return Path.home() / ".daniel_etterna"', source)
        app = (ROOT / "src" / "daniel_etterna.py").read_text(encoding="utf-8")
        self.assertIn('"DanielBridge.txt"', app)
        for name in (
            "daniel_bridge.lua",
            "daniel_menu_bridge.lua",
            "daniel_gameplay_bridge.lua",
        ):
            self.assertTrue((ROOT / "bridges" / name).is_file())


if __name__ == "__main__":
    unittest.main()

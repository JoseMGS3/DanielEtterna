SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Español",
}

DEFAULT_LANGUAGE = "en"


STRINGS = {
    "en": {
        "settings_window_title": "DanielEtterna - Options",
        "settings_heading": "Options",
        "language": "Language",
        "language_hint": "Interface language. Changes are applied when you save.",
        "etterna_path": "Etterna path",
        "browse": "Browse...",
        "browse_title": "Select Etterna root folder",
        "path_hint": "Select the folder that contains Save, Songs and Themes.",
        "keybinds": "Keybinds",
        "keybind_hint": "Click a field, then press the key or combination you want to use.",
        "keybind_capture_hint": "Press a key or combination...",
        "always_on_top": "Always on top",
        "cycle_mode": "Change layout",
        "open_settings": "Open options",
        "restore_keybinds": "Restore keybinds",
        "config_path": "Save file: {path}",
        "cancel": "Cancel",
        "save": "Save",
        "etterna_path_error_title": "Etterna path",
        "keybind_error_title": "Invalid keybind",
        "save_error_title": "Save error",
        "configure_path": "Configure Etterna path",
        "waiting_bridge": "Waiting for Etterna bridge...",
        "waiting_chart": "Etterna connected - waiting for chart",
        "msd_error": "MSD Error",
        "estimated_dan": "Est. Dan:",
        "invalid_beatmap": "Invalid Beatmap/File",
        "select_etterna_root": "Select the Etterna root folder.",
        "folder_missing": "The selected folder does not exist.",
        "not_folder": "The selected path is not a folder.",
        "save_missing": "The 'Save' folder was not found. Select the Etterna root folder.",
        "valid_path": "Valid path.",
        "keybind_must_text": "The keybind must be text.",
        "keybind_empty": "The keybind is empty.",
        "invalid_keybind": "Invalid keybind: {spec}",
        "unknown_key": "Unknown key: {key}",
        "missing_key": "Missing key in: {spec}",
        "duplicate_keybind": "Two actions cannot use the same keybind: {a} and {b}.",
    },
    "es": {
        "settings_window_title": "DanielEtterna - Opciones",
        "settings_heading": "Opciones",
        "language": "Idioma",
        "language_hint": "Idioma de la interfaz. Los cambios se aplican al guardar.",
        "etterna_path": "Ruta de Etterna",
        "browse": "Examinar...",
        "browse_title": "Selecciona la carpeta raíz de Etterna",
        "path_hint": "Selecciona la carpeta que contiene Save, Songs y Themes.",
        "keybinds": "Keybinds",
        "keybind_hint": "Haz clic en un campo y luego presiona la tecla o combinación que quieras usar.",
        "keybind_capture_hint": "Presiona una tecla o combinación...",
        "always_on_top": "Siempre adelante",
        "cycle_mode": "Cambiar layout",
        "open_settings": "Abrir opciones",
        "restore_keybinds": "Restaurar keybinds",
        "config_path": "Configuración: {path}",
        "cancel": "Cancelar",
        "save": "Guardar",
        "etterna_path_error_title": "Ruta de Etterna",
        "keybind_error_title": "Keybind inválida",
        "save_error_title": "Error al guardar",
        "configure_path": "Configura la ruta de Etterna",
        "waiting_bridge": "Esperando el bridge de Etterna...",
        "waiting_chart": "Etterna conectado - esperando chart",
        "msd_error": "Error de MSD",
        "estimated_dan": "Dan est.:",
        "invalid_beatmap": "Beatmap/File inválido",
        "select_etterna_root": "Selecciona la carpeta raíz de Etterna.",
        "folder_missing": "La carpeta seleccionada no existe.",
        "not_folder": "La ruta seleccionada no es una carpeta.",
        "save_missing": "No se encontró la carpeta 'Save'. Selecciona la carpeta raíz de Etterna.",
        "valid_path": "Ruta válida.",
        "keybind_must_text": "La keybind debe ser texto.",
        "keybind_empty": "La keybind está vacía.",
        "invalid_keybind": "Keybind inválida: {spec}",
        "unknown_key": "Tecla no reconocida: {key}",
        "missing_key": "Falta una tecla en: {spec}",
        "duplicate_keybind": "Dos acciones no pueden usar la misma tecla rápida: {a} y {b}.",
    },
}


def normalize_language(language):
    value = str(language or "").strip().lower()
    if value in SUPPORTED_LANGUAGES:
        return value
    return DEFAULT_LANGUAGE


def language_name(language):
    return SUPPORTED_LANGUAGES[normalize_language(language)]


def language_code_from_name(name):
    value = str(name or "").strip().lower()
    for code, display in SUPPORTED_LANGUAGES.items():
        if value == display.lower():
            return code
    return DEFAULT_LANGUAGE


def t(key, language=DEFAULT_LANGUAGE, **kwargs):
    language = normalize_language(language)
    text = STRINGS.get(language, STRINGS[DEFAULT_LANGUAGE]).get(
        key,
        STRINGS[DEFAULT_LANGUAGE].get(key, key),
    )
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text

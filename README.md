# DanielEtterna v1.1.1

A real-time rice difficulty calculator for 4k Etterna. Supports .osu, .ssc and .sm files. (Note: .sm/.ssc charts using WARPS are not currently supported.)

**Ratings below Alpha Dan are enabled, but can be inaccurate.**

**[Original Website](https://thebagelofman.github.io/Daniel/)** · **[Original Daniel](https://github.com/TheBagelOfMan/Daniel)** · **[Download DanielEtterna](https://github.com/JoseMGS3/DanielEtterna/releases)**

## Window layouts (v1.1.1)

The default window sizes are **Full: 650 x 407**, **Compact: 550 x 102**, and
**Statistics: 650 x 157**. Under **Options → General**, the 50%, 75%, and 100%
buttons scale the active layout relative to its default size.

The app saves the last window position when closed and maintains a separate
custom size for every layout. Switching layouts restores each layout's last
chosen size. The **Skins** tab (same name in English and Spanish) has empty
**Nomenclature** and **Skin** dropdowns reserved for future options.

# Keybinds 

- Always on top: F1
- Switch layout: Tab
- Open settings: Q

Keybinds are focus-only by default. On Windows, enable **Detect keybinds outside DanielEtterna** in **Options → General** if you want the shortcuts to work while Etterna or another app has focus.


## Linux build BROKEN DO NOT USE

Use `build_linux.sh` to create a Linux binary:

```bash
./build_linux.sh
```

This script installs dependencies using python venv and outputs `dist/Daniel-linux`. If `src/msd` is missing, set `MSD_BIN_PATH` at runtime to a Linux-compatible `msd` executable.

On Linux/macOS, it will use Wine if only `src/msd.exe` is available.

## License

[MIT](LICENSE)

## Nomenclature profiles (Default / MMA / --/++ / Mania tracker)

In **Options → Skins → Nomenclature** you can choose:

- **Default** — the original DanielEtterna labels and numeric ratings, unchanged.
- **MMA** — Mania Map Analyser's Reform/Greek names and five tiers
  (`low`, `mid/low`, `mid`, `mid/high`, `high`). Its displayed numeric
  scale is shifted by **−0.5** from the original DanielEtterna numeric:
  10.5 = Alpha low, 11.0 = Alpha mid, 11.5 = Beta low.
- **--/++** — MMA's five subdivisions shown as suffixes, with **no numeric
  offset**: `low → --`, `mid/low → -`, `mid → (no suffix)`,
  `mid/high → +`, `high → ++`. Examples: `9.1 → 9--`,
  `9.5 → 9`, `9.8 → 9++`, `11.8 → Alpha++`.
  Reform numeric Dans appear as plain numbers. Because Windows prohibits
  `/` in filenames, the editable JSON is named `PlusMinus.json`; the
  selector displays `--/++`.
- **Mania tracker** — exactly the same Dan names, five subdivisions,
  and centered thresholds as MMA, but with **no numeric offset**.
  Examples: `10.5 → Alpha low`, `11.0 → Alpha mid`,
  `11.5 → Beta low`. Its editable file is `Mania tracker.json`.

The settings are saved to `%LOCALAPPDATA%\\DanielEtterna\\config.json`.
On first use, editable profile files are installed to
`%LOCALAPPDATA%\\DanielEtterna\\nomenclatures\\`. Existing files are never
overwritten by an update. The source templates are in
`src/nomenclatures/`. In a one-file executable, Python fallback definitions
ensure all built-in profiles are available even if JSON files were not bundled.

Changing the nomenclature only changes displayed text and the numeric scale;
it does **not** change the underlying SR calculation. The original Daniel
estimator still ends at Theta; additional MMA names are defined for future
compatibility, not as support for rating charts above that limit.

## Theme compatibility

DanielEtterna is currently developed and tested with Rebirth theme.
Other themes may be compatible, but their `ScreenSelectMusic` and `ScreenGameplay` implementations can differ. The three Lua bridge actors must be loaded by the equivalent screens of the selected theme, and theme-specific rate/preview functions may require adaptation.


# How to build

1. Install requirements with pip:

```cmd
pip install -r requirements.txt
```

2. Open cmd on `DanielEtterna-main\src` then paste:

```cmd
pyinstaller --clean --noconfirm --onefile --windowed --name DanielEtterna --icon=icon.ico --add-data "icon.ico;." daniel_etterna.py
```

If you want the debug window instead, then paste:

```cmd
pyinstaller --clean --noconfirm --onefile --name DanielEtterna --icon=icon.ico --add-data "icon.ico;." daniel_etterna.py
```

# INSTALATION

## 1. Lua Bridges

DanielEtterna needs three Lua scripts (briges) to receive information from Etterna; these can be found on the `/bridges` folder:

```
daniel_bridge.lua
daniel_menu_bridge.lua
daniel_gameplay_bridge.lua
```

These files must be copied into the theme you are using in Etterna.

## 1.11 daniel_bridge.lua

```
Etterna\
└── Themes\
    └── [YOUR THEME]\
        └── BGAnimations\
            └── ScreenSelectMusic decorations\
                └── daniel_bridge.lua
```

## 1.12 daniel_menu_bridge.lua

```
Etterna\
└── Themes\
    └── [YOUR THEME]\
        └── BGAnimations\
            └── ScreenSelectMusic decorations\
                └── daniel_menu_bridge.lua
```

## 1.13 ScreenSelectMusic decorations\default.lua

With a text editor (ej. notepad), `open default.lua` file, located on:

```
Etterna\
└── Themes\
    └── [YOUR THEME]\
        └── BGAnimations\
            └── ScreenSelectMusic decorations\
                └── default.lua
```

Near the end of `default.lua`, next to the others `LoadActor` but BEFORE `return t`, paste this text:

```
t[#t+1] = LoadActor("daniel_bridge.lua")
t[#t+1] = LoadActor("daniel_menu_bridge.lua")
```

## 1.21 daniel_gameplay_bridge.lua

```
Etterna\
└── Themes\
    └── [YOUR THEME]\
        └── BGAnimations\
            └── ScreenGameplay overlay\
                └── daniel_gameplay_bridge.lua
```


## 1.22 ScreenGameplay overlay\default.lua


Same as step 1.13, paste:

```
t[#t+1] = LoadActor("daniel_gameplay_bridge.lua")
```


## 1.3 Final structure

```
Etterna
└── Themes
    └── [YOUR THEME]
        └── BGAnimations
            │
            ├── ScreenSelectMusic decorations
            │   ├── default.lua
            │   ├── daniel_bridge.lua
            │   └── daniel_menu_bridge.lua
            │
            └── ScreenGameplay overlay
                ├── default.lua
                └── daniel_gameplay_bridge.lua
```

After completing the steps above, restart Etterna.




# EXPLANATION

DanielEtterna needs three Lua scripts (briges) to receive information from Etterna; these can be found on the `/bridges` folder:

```
daniel_bridge.lua
daniel_gameplay_bridge.lua
daniel_menu_bridge.lua
```

These files must be copied into the theme you are using in Etterna.


## 1. daniel_bridge.lua

It is responsible for sendinginformation about the selected file to DanielEtterna:

```
Song
Chart
Difficulty
Meter
Rate
.sm/.ssc/.osu file
Etterna MSD
Skillsets
```


## 2. daniel_menu_bridge.lua

This file provides the current position of the music while you're on the selection screen.

Allows the strain graph to advance while the preview is playing.


## 3. daniel_gameplay_bridge.lua

Responsible for sending the song's position during gameplay:

```
playing
music_seconds
rate
```

Thanks to this, the graph synchronizes with the song while you play.

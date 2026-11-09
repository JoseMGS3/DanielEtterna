# DanielEtterna v1.1.1

A real-time rice difficulty calculator for 4k Etterna. Supports .osu, .ssc and .sm files. (Note: .sm/.ssc charts using WARPS are not currently supported.)

**Ratings below Alpha Dan are enabled, but can be inaccurate.**

**[Original Website](https://thebagelofman.github.io/Daniel/)** · **[Original Daniel](https://github.com/TheBagelOfMan/Daniel)** · **[Download DanielEtterna](https://github.com/JoseMGS3/DanielEtterna/releases)**

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

## Nomenclature profiles (Default / MMA / --/++ / Mania tracker / Images)

In **Options → Skins → Nomenclature** you can choose:

- **Default** — the original DanielEtterna labels and numeric ratings, unchanged.
- **MMA** — Mania Map Analyser's Reform/Greek names and five tiers
  (`low`, `mid/low`, `mid`, `mid/high`, `high`).
  Every integer is the **center** of a Dan: `11.0 → Alpha mid`,
  `12.0 → Beta mid`. The first half of the next Dan begins at .5,
  so `10.5 → Alpha low` and `11.5 → Beta low`. This is a half-Dan
  shift of **naming boundaries relative to Default**, not a subtraction
  from the displayed numeric DP. Existing old MMA.json files with a
  `-0.5` offset are interpreted using the corrected centered scale
  without overwriting custom Dan names.
- **--/++** — MMA's five subdivisions shown as suffixes, with **no numeric
  offset**: `low → --`, `mid/low → -`, `mid → (no suffix)`,
  `mid/high → +`, `high → ++`. Examples: `9.1 → 9--`,
  `9.5 → 9`, `9.8 → 9++`, `11.8 → Alpha++`.
  Reform numeric Dans appear as plain numbers. Because Windows prohibits
  `/` in filenames, the editable JSON is named `PlusMinus.json`; the
  selector displays `--/++`.
- **Mania tracker** — uses the same Dan names and five subdivisions
  as MMA, with **no numeric offset** and integer-based intervals.
  The fraction of each integer Dan determines the tier: `.00–.19 low`,
  `.20–.39 mid/low`, `.40–.59 mid`, `.60–.79 mid/high`,
  `.80–.99 high`. Examples: `11.14 → Alpha low` and
  `12.08 → Beta low`. Its editable file is `Mania tracker.json`.
  Previously installed `centered` Mania tracker files are interpreted
  using the corrected intervals without overwriting personal edits.
- **Images** — uses the same five subdivisions as Mania tracker. Each name
  is replaced with an uploaded Reform badge if present, with the original
  numeric DP alongside it. Missing images fall back to readable text.
  The 100 Reform assets have been uploaded to `src/nomenclatures/images/`
  on branch `v1.1.1`. A source run finds them automatically. For Windows
  EXEs, the files must be included in the build or copied to the writable
  `%LOCALAPPDATA%\\DanielEtterna\\nomenclatures\\images\\` directory.
  The app also checks for assets next to the executable and in a nearby
  Git checkout. The Skins menu displays only the selectable nomenclature
  cards and their examples, without asset counters or folder controls.
  The Windows build first converts numbered Dans (1–10) from SVG to PNG
  using the Windows-compatible `svg2png-py` renderer (no native Cairo DLL).
  At runtime, Pillow loads these generated PNGs and the Greek WebP badges.
  The original SVG files are preserved. When running directly from Python
  without generated PNGs, the application can render SVGs using svg2png-py.

  Build from the repository root with `build_windows.bat`. The included
  batch script creates 50 PNG images and packages those alongside the
  100 original SVG/WebP files. You must rebuild an older EXE to get them.

The settings are saved to `%LOCALAPPDATA%\\DanielEtterna\\config.json`.
On first use, editable profile files are installed to
`%LOCALAPPDATA%\\DanielEtterna\\nomenclatures\\`. Existing files are never
overwritten by an update. The source templates are in
`src/nomenclatures/`. In a one-file executable, Python fallback definitions
ensure all built-in profiles are available even if JSON files were not bundled.

Changing the nomenclature only changes the Dan label; it leaves the numeric
rating and the underlying SR calculation unchanged. The original Daniel
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

2. From the **repository root**, double-click `build_windows.bat`.
   It installs the Windows SVG renderer, converts the 50 numbered SVGs to
   PNG and generates `dist/DanielEtterna.exe` with all rank artwork.

   If you prefer to build manually, run the following in the root:

```cmd
py scripts/prepare_reform_png.py
pyinstaller --clean --noconfirm --onefile --windowed --name DanielEtterna --icon "src/icon.ico" --add-data "src/icon.ico;." --add-data "src/nomenclatures/images;nomenclatures/images" src/daniel_etterna.py
```

   To keep the debug console, remove `--windowed`.

   **Troubleshooting missing rank badges:** place the assets under
   `%LOCALAPPDATA%\\DanielEtterna\\nomenclatures\\images\\` or rebuild
   the EXE with `build_windows.bat`. A previously compiled EXE does not
   automatically receive images uploaded to GitHub. Restart Options
   to refresh the Images sample.


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

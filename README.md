# Ethan

Ethan is the renamed DanielEtterna app, a real-time difficulty calculator for 4K Etterna with Legacy and XDC1 engines. Supports .osu, .ssc and .sm files. (Note: .sm/.ssc charts using WARPS are not currently supported.)

**Ratings below Alpha Dan are enabled, but can be inaccurate.**

**[Original Website](https://thebagelofman.github.io/Daniel/)** · **[Original Daniel](https://github.com/TheBagelOfMan/Daniel)** · **[Releases (DanielEtterna repository)](https://github.com/JoseMGS3/DanielEtterna/releases)**

# Keybinds 

- Always on top: F1
- Switch layout: Tab
- Open settings: Q



## Linux build BROKEN DO NOT USE

Use `build_linux.sh` to create a Linux binary:

```bash
./build_linux.sh
```

This script installs dependencies using python venv and outputs `dist/Ethan-linux`. If `src/msd` is missing, set `MSD_BIN_PATH` at runtime to a Linux-compatible `msd` executable.

On Linux/macOS, it will use Wine if only `src/msd.exe` is available.

## Name and settings compatibility

The application/window and new Windows executable are named **Ethan**.
The GitHub repository, Python entry point (`src/daniel_etterna.py`) and
Etterna bridge filenames retain their original names for compatibility.
Existing settings and custom assets remain at
`%LOCALAPPDATA%\\DanielEtterna\\` on Windows (or
`~/.daniel_etterna/` on Linux); there is no reset or migration required.
Existing `DanielEtterna.exe` builds remain separate from the new `Ethan.exe`.

## License

[MIT](LICENSE)

## Theme compatibility

Ethan is currently developed and tested with Rebirth theme.
Other themes may be compatible, but their `ScreenSelectMusic` and `ScreenGameplay` implementations can differ. The three Lua bridge actors must be loaded by the equivalent screens of the selected theme, and theme-specific rate/preview functions may require adaptation.


# How to build

1. Install requirements with pip:

```cmd
pip install -r requirements.txt
```

2. On `main`/1.1.1, `build_windows.bat` produces the historical `dist/DanielEtterna.exe`. On `2.0-dev`, it compiles and packages XDC1 (Visual Studio Build Tools C++ required) and produces **`dist/Ethan.exe`**. For a debug build, use `build_debug_windows.bat` to produce `dist/Ethan-Debug.exe`.

   If you prefer to build manually, run the following in the root.
   On `2.0-dev`, first run `build_xdc1.bat` to compile the new C++ engine:

```cmd
build_xdc1.bat
py scripts/prepare_reform_png.py
pyinstaller --clean --noconfirm --onefile --windowed --name Ethan --icon "src/icon.ico" --add-data "src/icon.ico;." --add-data "src/nomenclatures/images;nomenclatures/images" --add-data "src/xdc1.exe;." src/daniel_etterna.py
```

   To keep the debug console, remove `--windowed`.

   **Troubleshooting missing rank badges:** place the assets under
   `%LOCALAPPDATA%\\DanielEtterna\\nomenclatures\\images\\` or rebuild
   the EXE with `build_windows.bat`. A previously compiled EXE does not
   automatically receive images uploaded to GitHub. Restart Options
   to refresh the Images sample.


# INSTALATION

## 1. Lua Bridges

Ethan needs three Lua scripts (briges) to receive information from Etterna; these can be found on the `/bridges` folder:

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

Ethan needs three Lua scripts (briges) to receive information from Etterna; these can be found on the `/bridges` folder:

```
daniel_bridge.lua
daniel_gameplay_bridge.lua
daniel_menu_bridge.lua
```

These files must be copied into the theme you are using in Etterna.


## 1. daniel_bridge.lua

It is responsible for sending information about the selected file to Ethan:

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

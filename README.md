# DanielEtterna

## Version 1.1

- Clears stale Etterna bridge state on startup so the previous chart is not shown.
- Remembers the last selected layout.
- Adds Small / Medium / Large preset window sizes in Options.
- Responsive text automatically shrinks when the window is too narrow.
- The strain graph keeps updating even when the current layout hides it.
- Options now includes a separate Style tab reserved for future customization.
- The Options window is resizable, uses larger borderless tabs, and its controls/text reflow and scale with the window.
- Keybinds are focus-only by default; on Windows, Options → General can enable detection while another app has focus.


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

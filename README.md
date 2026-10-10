# GTA San Andreas Mode Launcher

A small Windows launcher for **GTA: San Andreas** that switches between two mod
sets, **Story** (single player) and **SAMP** (multiplayer), with one click.

If you play single player with mods and also play SAMP with other mods that
conflict with them, you no longer need to add and remove files by hand: pick a
mode, press **Play**, and the launcher swaps the right files and starts the game.

This program was created primarily for my "SA Definitive Modpack" project, which you can find here:
https://sadefinitivemodpack.blogspot.com/

## Features

- Simple interface: choose **Story** or **SAMP** and press **Play**.
- Verifies that all files of the current mode are present before changing anything.
- Supports mods inside subfolders (the folder structure is mirrored).
- Skips the file swap when the selected mode is already loaded.
- Refuses to switch while the game is running.
- Recovers automatically if a switch was interrupted.
- Never overwrites original game files.
- Portable: uses relative paths only, no installation needed.

## Requirements

- Windows
- A legitimate copy of GTA: San Andreas (`gta_sa.exe`)
- [SA-MP](https://sa-mp.app/) installed (`samp.exe`) if you want to use SAMP mode

## Installation

1. Download `GTA_SA_Launcher.exe` from the [Releases](../../releases) page.
2. Put it in the **root folder of your game** (next to `gta_sa.exe`).
3. Create these folders next to it (or download the ready-made `launcher` folder from the release):

```
GTA San Andreas/
├── GTA_SA_Launcher.exe
├── gta_sa.exe
├── samp.exe
└── launcher/
    ├── story/     <- files of your Story mods
    ├── samp/      <- files of your SAMP mods
    └── images/    <- story.png and samp.png (240x320), optional icon.ico
```

4. **Copy** (don't move) your mod files into `launcher/story` or `launcher/samp`.

### Important: mirror the game's folder structure

Files inside `launcher/story` and `launcher/samp` must follow the same paths they
have in the game folder:

```
launcher/story/scripts/mymod.cs   ->   <game folder>/scripts/mymod.cs
launcher/samp/samp.dll            ->   <game folder>/samp.dll
```

The game folder should start with the **Story** mods loaded.

## How it works

When you switch from mode A to mode B:

1. It checks that every file in `launcher/A` exists in the game folder.
2. It checks that the files of B won't overwrite unrelated game files.
3. It moves A's files from the game folder back into `launcher/A`.
4. It copies B's files from `launcher/B` into the game folder.
5. It launches `gta_sa.exe` (Story) or `samp.exe` (SAMP).

Your `launcher` folder always keeps a complete copy of each mod set, and any
config changes made while playing are preserved. The current mode is stored in
`launcher/state.json`.

## Configuration (optional)

Create `launcher/config.json`:

```json
{ "close_after_launch": false }
```

| Option | Default | Description |
|---|---|---|
| `close_after_launch` | `true` | Close the launcher after starting the game |

## Troubleshooting

| Message | Solution |
|---|---|
| *Some files of the loaded mode are missing* | A mod file was deleted from the game folder. Restore it or remove it from `launcher/<mode>`. |
| *Files would be overwritten* | A mod replaces an original game file. Remove it from the mod folder or handle it manually. |
| *Game is currently running* | Close `gta_sa.exe` / `samp.exe` first. |
| *A file operation failed* | Close programs using the game files. If the game is in `Program Files`, run the launcher as administrator. |

## Building from source

Requires Python 3.10+ with tkinter.

```
git clone https://github.com/CriztoKortez/GTA-San-Andreas-Mode-Launcher.git
cd GTA-San-Andreas-Mode-Launcher
build.bat
```

The executable will be created in `dist/GTA_SA_Launcher.exe`.

## Disclaimer

This project is not affiliated with or endorsed by Rockstar Games or the SA-MP
team. It does not include any game files, mods, or Rockstar artwork. You need
your own copy of the game. Back up your game folder before using it.

## License

[MIT](LICENSE)

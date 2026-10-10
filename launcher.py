"""
GTA San Andreas Mode Launcher
=============================

Switches between "Story" and "SAMP" mod sets and starts the right executable.

Expected folder layout (the launcher .exe lives in the game's root folder):

    <GTA San Andreas root>/
        GTA_SA_Launcher.exe
        gta_sa.exe
        samp.exe
        launcher/
            story/            <- files of the Story mod set
            samp/             <- files of the SAMP mod set
            images/           <- story.png, samp.png (and optional icon.ico)
            state.json        <- created automatically (remembers loaded mode)
            config.json       <- optional settings

Files inside launcher/story and launcher/samp must mirror the game's folder
structure. Example:  launcher/story/scripts/mymod.cs  <->  <root>/scripts/mymod.cs

How a switch works (A = loaded mode, B = target mode):
    1. Verify every file of launcher/A exists in the game folder.
    2. Check B's files will not overwrite unrelated game files.
    3. Move A's files from the game folder back into launcher/A
       (so the launcher folder always keeps a full copy and any change you
       made to a config file while playing is preserved).
    4. Copy B's files from launcher/B into the game folder.
    5. Remember B as the loaded mode and launch the game.
"""

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox

APP_TITLE = "GTA San Andreas Launcher"

# --------------------------------------------------------------------------
# Paths (all relative to the folder where the launcher lives)
# --------------------------------------------------------------------------


def get_root_dir():
    """Folder of the .exe (when frozen by PyInstaller) or of this script."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


ROOT_DIR = get_root_dir()
LAUNCHER_DIR = os.path.join(ROOT_DIR, "launcher")
IMAGES_DIR = os.path.join(LAUNCHER_DIR, "images")
STATE_FILE = os.path.join(LAUNCHER_DIR, "state.json")
CONFIG_FILE = os.path.join(LAUNCHER_DIR, "config.json")

MODES = {
    "story": {"label": "Story", "exe": "gta_sa.exe", "image": "story.png"},
    "samp": {"label": "SAMP", "exe": "samp.exe", "image": "samp.png"},
}
DEFAULT_MODE = "story"

# Files that are never treated as mods.
IGNORED_FILES = {"desktop.ini", "thumbs.db", ".gitkeep", ".ds_store"}

# Vanilla folders that must never be removed, even if they end up empty.
PROTECTED_DIRS = {
    "data", "models", "audio", "anim", "movies", "text", "userfiles",
    "gta san andreas user files", "launcher",
}

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class LauncherError(Exception):
    """An error whose message is safe to show to the user."""


# --------------------------------------------------------------------------
# State / config
# --------------------------------------------------------------------------


def mode_dir(mode):
    return os.path.join(LAUNCHER_DIR, mode)


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("mode") in MODES:
            if data.get("target") not in MODES:
                data.pop("target", None)
            return data
    except (OSError, ValueError, AttributeError):
        pass
    return {"mode": DEFAULT_MODE}  # the game folder ships with Story loaded


def save_state(mode, target=None):
    data = {"mode": mode}
    if target:
        data["target"] = target  # marks a switch in progress
    tmp = STATE_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, STATE_FILE)
    except OSError as e:
        raise LauncherError(f"Could not write launcher/state.json:\n{e}")


def load_config():
    config = {"close_after_launch": True}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config.update(json.load(f))
    except (OSError, ValueError):
        pass
    return config


# --------------------------------------------------------------------------
# File helpers
# --------------------------------------------------------------------------


def list_mod_files(mode):
    """Relative paths of every file inside launcher/<mode> (subfolders included)."""
    base = mode_dir(mode)
    files = []
    for dirpath, _dirs, names in os.walk(base):
        for name in names:
            if name.lower() in IGNORED_FILES:
                continue
            files.append(os.path.relpath(os.path.join(dirpath, name), base))
    return sorted(files)


def move_file(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        os.replace(src, dst)  # fast path, same drive
    except OSError:
        shutil.copy2(src, dst)
        os.remove(src)


def prune_empty_dirs(rel_files):
    """Remove folders left empty after taking a mod set out of the game folder."""
    dirs = set()
    for rel in rel_files:
        d = os.path.dirname(rel)
        while d:
            dirs.add(d)
            d = os.path.dirname(d)
    for d in sorted(dirs, key=lambda x: x.count(os.sep), reverse=True):
        if d.lower() in PROTECTED_DIRS:
            continue
        full = os.path.join(ROOT_DIR, d)
        try:
            if os.path.isdir(full) and not os.listdir(full):
                os.rmdir(full)
        except OSError:
            pass


def format_list(items, limit=8):
    shown = "\n".join(f"  - {i}" for i in items[:limit])
    if len(items) > limit:
        shown += f"\n  ...and {len(items) - limit} more"
    return shown


def is_process_running(exe_name):
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/NH"],
            capture_output=True, text=True, creationflags=CREATE_NO_WINDOW,
        ).stdout
        return exe_name.lower() in out.lower()
    except OSError:
        return False


# --------------------------------------------------------------------------
# Core logic
# --------------------------------------------------------------------------


def preflight(target):
    """Checks that must pass before touching anything."""
    if not os.path.isdir(LAUNCHER_DIR):
        raise LauncherError("The 'launcher' folder was not found next to the launcher.")
    for mode in MODES:
        if not os.path.isdir(mode_dir(mode)):
            raise LauncherError(f"The folder 'launcher\\{mode}' was not found.")

    for exe in ("gta_sa.exe", "samp.exe"):
        if is_process_running(exe):
            raise LauncherError(
                f"{exe} is currently running.\nClose the game before launching or switching modes."
            )

    target_files = {os.path.normcase(f) for f in list_mod_files(target)}
    required = ["gta_sa.exe"] + (["samp.exe"] if target == "samp" else [])
    for exe in required:
        in_game_folder = os.path.isfile(os.path.join(ROOT_DIR, exe))
        if not in_game_folder and os.path.normcase(exe) not in target_files:
            raise LauncherError(f"{exe} was not found in the game folder.")


def switch_mode(current, target, resume=False):
    """Switch the game folder from mod set `current` to mod set `target`."""
    files_a = list_mod_files(current)
    files_b = list_mod_files(target)
    a_set = {os.path.normcase(r) for r in files_a}

    if not resume:
        # 1. Every file of the loaded mode must be in the game folder.
        missing = [r for r in files_a if not os.path.isfile(os.path.join(ROOT_DIR, r))]
        if missing:
            raise LauncherError(
                f"Some files of the loaded mode ('{current}') are missing from the game folder:\n"
                f"{format_list(missing)}\n\nNothing was changed. Restore those files "
                f"(or remove them from launcher\\{current}) and try again."
            )
        # 2. The new mode must not overwrite unrelated game files.
        conflicts = [
            r for r in files_b
            if os.path.normcase(r) not in a_set and os.path.exists(os.path.join(ROOT_DIR, r))
        ]
        if conflicts:
            raise LauncherError(
                f"These files from launcher\\{target} already exist in the game folder "
                f"and would be overwritten:\n{format_list(conflicts)}\n\nNothing was changed."
            )

    # From here on, a crash leaves a marker so the next run can finish the job.
    save_state(current, target)

    try:
        # 3. Take the loaded mode's files out of the game folder.
        for rel in files_a:
            src = os.path.join(ROOT_DIR, rel)
            if os.path.isfile(src):
                move_file(src, os.path.join(mode_dir(current), rel))
        prune_empty_dirs(files_a)

        # 4. Bring the new mode's files in.
        for rel in files_b:
            dst = os.path.join(ROOT_DIR, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(mode_dir(target), rel), dst)
    except OSError as e:
        raise LauncherError(
            f"A file operation failed while switching modes:\n{e}\n\n"
            "Close any program using the game files (or run the launcher as "
            "administrator if the game is in 'Program Files') and press Play "
            "again; the launcher will finish the switch."
        )

    save_state(target)


def ensure_mode(target):
    state = load_state()
    current = state["mode"]
    pending = state.get("target")
    if pending:  # a previous switch was interrupted: finish it first
        switch_mode(current, pending, resume=True)
        current = pending
    if current != target:
        switch_mode(current, target)


def launch_game(target):
    exe_path = os.path.join(ROOT_DIR, MODES[target]["exe"])
    if not os.path.isfile(exe_path):
        raise LauncherError(f"{MODES[target]['exe']} was not found in the game folder.")
    if target == "samp" and not os.path.isfile(os.path.join(ROOT_DIR, "gta_sa.exe")):
        raise LauncherError("gta_sa.exe was not found in the game folder.")
    try:
        os.startfile(exe_path, cwd=ROOT_DIR)  # Windows only; Python 3.10+
    except OSError as e:
        raise LauncherError(f"Could not start {MODES[target]['exe']}:\n{e}")


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------

BG = "#14161a"
CARD_BG = "#1f2329"
FG = "#e8eaed"
MUTED = "#8b929c"
ACCENT = "#e8a317"
ACCENT_DARK = "#b97f0a"
CARD_W, CARD_H = 240, 320


class LauncherApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.configure(bg=BG)
        self.resizable(False, False)
        self._set_icon()

        self.config_data = load_config()
        self.selected = load_state()["mode"]
        self.busy = False
        self.images = {}
        self.cards = {}
        self.results = queue.Queue()

        self._build_ui()
        self._refresh()
        self._center()
        self.after(100, self._poll)

    # ---- construction ----------------------------------------------------

    def _set_icon(self):
        icon = os.path.join(IMAGES_DIR, "icon.ico")
        if os.path.isfile(icon):
            try:
                self.iconbitmap(icon)
            except tk.TclError:
                pass

    def _build_ui(self):
        tk.Label(self, text="GTA: SAN ANDREAS", font=("Segoe UI", 20, "bold"),
                 fg=FG, bg=BG).pack(pady=(22, 0))
        tk.Label(self, text="Select a game mode", font=("Segoe UI", 10),
                 fg=MUTED, bg=BG).pack(pady=(0, 16))

        row = tk.Frame(self, bg=BG)
        row.pack(padx=30)
        for index, (key, info) in enumerate(MODES.items()):
            self._build_card(row, key, info, index)

        self.status = tk.Label(self, text="", font=("Segoe UI", 10),
                               fg=MUTED, bg=BG, wraplength=520)
        self.status.pack(pady=(18, 6))

        self.play_btn = tk.Button(
            self, text="PLAY", font=("Segoe UI", 14, "bold"), width=18,
            bg=ACCENT, fg="#101010", activebackground=ACCENT_DARK,
            activeforeground="#101010", relief="flat", cursor="hand2",
            command=self.on_play,
        )
        self.play_btn.pack(pady=(0, 24), ipady=6)

    def _build_card(self, parent, key, info, column):
        frame = tk.Frame(parent, bg=BG)
        frame.grid(row=0, column=column, padx=16)

        canvas = tk.Canvas(frame, width=CARD_W, height=CARD_H, bg=CARD_BG,
                           highlightthickness=4, cursor="hand2")
        canvas.pack()

        image = self._load_image(info["image"])
        if image:
            self.images[key] = image  # keep a reference or Tk drops it
            canvas.create_image(CARD_W // 2, CARD_H // 2, image=image)
        else:
            canvas.create_text(CARD_W // 2, CARD_H // 2, text=info["label"].upper(),
                               fill=FG, font=("Segoe UI", 22, "bold"))

        label = tk.Label(frame, text=info["label"], font=("Segoe UI", 13, "bold"),
                         fg=FG, bg=BG, cursor="hand2")
        label.pack(pady=(8, 0))

        for widget in (canvas, label):
            widget.bind("<Button-1>", lambda _e, k=key: self.select(k))
        self.cards[key] = canvas

    @staticmethod
    def _load_image(filename):
        path = os.path.join(IMAGES_DIR, filename)
        if not os.path.isfile(path):
            return None
        try:
            return tk.PhotoImage(file=path)  # PNG/GIF, recommended size 240x320
        except tk.TclError:
            return None

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")

    # ---- state display ---------------------------------------------------

    def select(self, mode):
        if self.busy:
            return
        self.selected = mode
        self._refresh()

    def _refresh(self):
        for key, canvas in self.cards.items():
            canvas.configure(highlightbackground=ACCENT if key == self.selected else CARD_BG,
                             highlightcolor=ACCENT)
        if self.busy:
            return
        state = load_state()
        loaded = MODES[state["mode"]]["label"]
        if state.get("target"):
            text = "A previous mode switch was interrupted. It will be finished when you press Play."
        elif state["mode"] != self.selected:
            text = (f"Currently loaded: {loaded}. "
                    f"Files will be swapped to {MODES[self.selected]['label']} when you press Play.")
        else:
            text = f"Currently loaded: {loaded}"
        self.status.configure(text=text)
        self.play_btn.configure(state="normal")

    def _set_busy(self, busy, text=""):
        self.busy = busy
        if busy:
            self.status.configure(text=text)
            self.play_btn.configure(state="disabled")
            self.config(cursor="watch")
        else:
            self.config(cursor="")
            self._refresh()

    # ---- actions ---------------------------------------------------------

    def on_play(self):
        if self.busy:
            return
        target = self.selected
        try:
            preflight(target)
        except LauncherError as e:
            messagebox.showerror(APP_TITLE, str(e))
            return

        state = load_state()
        if not state.get("target") and state["mode"] == target:
            self._launch(target)  # already loaded: skip verify/move
            return

        self._set_busy(True, f"Switching to {MODES[target]['label']} mode, please wait...")
        threading.Thread(target=self._worker, args=(target,), daemon=True).start()

    def _worker(self, target):
        try:
            ensure_mode(target)
            self.results.put(("ok", target))
        except LauncherError as e:
            self.results.put(("error", str(e)))
        except Exception as e:  # noqa: BLE001 - last-resort safety net
            self.results.put(("error", f"Unexpected error while switching modes:\n{e}"))

    def _poll(self):
        try:
            kind, payload = self.results.get_nowait()
        except queue.Empty:
            self.after(100, self._poll)
            return
        self._set_busy(False)
        if kind == "ok":
            self._launch(payload)
        else:
            messagebox.showerror(APP_TITLE, payload)
        self.after(100, self._poll)

    def _launch(self, target):
        try:
            launch_game(target)
        except LauncherError as e:
            messagebox.showerror(APP_TITLE, str(e))
            self._refresh()
            return
        if self.config_data.get("close_after_launch", True):
            self.destroy()
        else:
            self._refresh()


def main():
    LauncherApp().mainloop()


if __name__ == "__main__":
    main()

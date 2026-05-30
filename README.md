# 🧰 Tmux Tray — System Tray Monitor for Tmux Sessions

Tmux Tray is a lightweight **Python + Qt6 (PySide6)** application that sits in your system tray and provides a dynamic overview of your running **tmux** sessions. It lets you attach, restart, and kill sessions directly from the tray, and lets you register scripts to launch in tmux at login — all without opening a terminal.

---

## ✨ Features

* ✅ **Live session list** — detects all tmux sessions dynamically.
* 🖱️ **Tray-based control** — open, restart, or kill sessions with a click.
* 💬 **Hover preview** — tooltip shows the last lines of the selected pane.
* ⚙️ **Selectable focus** — choose which session the tooltip follows.
* 🚀 **Startup Tmux** — register scripts to launch in tmux at login, with auto-detection of self-tmux scripts and interpreter-prefix suggestion (`python3 …`, `node …`).
* 🔁 **Bidirectional XDG autostart sync** — toggling an entry in KDE Autostart reflects back into the app, and vice versa.
* 🛡️ **Conservative by design** — Start now never duplicates a running process; it warns with PID details instead.
* 🔄 **Cross-desktop compatible** — designed for KDE Plasma 6 (Wayland) but works elsewhere via XDG standards.
* 🧩 **Lightweight** — no background daemons, no bloat.

---

## 🧭 Compatibility

| Component               | Minimum                           | Tested On                          | Notes                                                |
| ----------------------- | --------------------------------- | ---------------------------------- | ---------------------------------------------------- |
| **OS**                  | Linux                             | Garuda Linux (Arch)                | XDG-compliant only. macOS/Windows are not supported. |
| **Desktop Environment** | KDE Plasma 6 / GNOME / XFCE       | ✅ KDE Plasma 6 (Wayland)           | GNOME needs the *AppIndicator* extension             |
| **Session Type**        | X11 or Wayland                    | ✅ Wayland                          | Uses StatusNotifierItem (SNI)                        |
| **Python**              | 3.11+                             | ✅ 3.14                             | Stdlib `tomllib` is required                         |
| **PySide6**             | 6.5+                              | ✅ 6.11                             | Strict enum checking honoured                        |
| **tmux**                | any recent release                | ✅ 3.4                              |                                                      |
| **Terminal Emulator**   | Konsole                           | ✅ Konsole                          | Hard-coded for now; PR-friendly                      |

---

## ⚙️ Installation

### Arch / Manjaro / Garuda

```bash
cd packaging
makepkg -si
```

### Debian / Ubuntu / Mint, Fedora / openSUSE / RHEL

Build host needs `fpm` (Ruby gem) and `uv`:

```bash
gem install --user-install fpm
./packaging/build-packages.sh             # produces dist/*.deb and dist/*.rpm
sudo apt install ./dist/tmux-tray_*.deb        # Debian family
sudo dnf install ./dist/tmux-tray-*.rpm        # Fedora family
sudo zypper install ./dist/tmux-tray-*.rpm     # openSUSE
```

After install, launch from your application menu or run `tmux-tray &`.

### From source (development)

Requires [`uv`](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/walterdemacedorodrigues/tmux-tray-manager.git
cd tmux-tray-manager
uv sync
uv run tmux-tray            # add --debug for verbose stderr logs
```

> **Dev-mode caveat:** without a system install the taskbar icon falls back
> to the Wayland generic icon — KDE Plasma needs `tmux-tray.desktop` in
> `/usr/share/applications/` to resolve the icon via `app_id`. The window
> decoration icon still uses the bundled SVG.

---

## 🧩 How It Works

* Polls `tmux ls` every 10 seconds via a Qt timer (2-second per-call timeout, so a stale socket can't freeze the UI).
* Tray icon swaps between:
  * 🟢 **emblem-success** — one or more sessions running
  * 🔴 **emblem-error** — no sessions
* Tooltip on hover shows the tail of the selected session's pane.
* Double-click attaches the most-recent session in a terminal (Konsole by default).
* Right-click menu, top to bottom:
  * **Startup Tmux…** — opens the autostart manager (see below)
  * **Hover session** — submenu picking which session the tooltip follows
  * **&lt;session&gt;** — per-session submenu: `open`, `restart`, `kill`
  * **Quit**

---

## 🚀 Startup Tmux

Manage scripts that should be launched inside tmux at login.

### Storage
* `~/.config/tmux-tray/startup.toml` — your registry (one TOML table per entry).
* `~/.config/autostart/tmux-tray-startup-<id>.desktop` — one XDG autostart entry per registered script, calling `tmux-tray --start <id>`. Visible in KDE's *Autostart* settings, GNOME Tweaks, etc.

### Adding an entry
The Add wizard:
1. Lets you pick a script (file picker or paste a path).
2. Runs three redundancy checks and reports them inline:
   * **Self-tmux detection** — grep for `tmux new-session`, `tmux attach`, `exec tmux`, etc. If positive, suggests mode `self-managed` so we don't wrap an already-wrapping script.
   * **XDG autostart scan** — warns if any other `*.desktop` in `~/.config/autostart/` already launches this script.
   * **Running processes** — reports current PIDs whose cmdline matches the script.
3. Auto-fills **Name**, **ID**, **Working directory**, and **Tmux session name** from the path. Uses the parent directory when the filename is generic (`run.sh`, `start.sh`, …).
4. **Command** — optional override that lets you prefix an interpreter. Auto-suggested from the extension:

   | Extension | Suggestion |
   | --- | --- |
   | `.py` | `python3 <abs-path>` |
   | `.js` / `.mjs` / `.cjs` | `node <abs-path>` |
   | `.rb` | `ruby <abs-path>` |
   | `.pl` | `perl <abs-path>` |
   | `.php` | `php <abs-path>` |
   | `.sh` / binary | (left empty — run directly) |

### Execution modes
* `tmux-wrapped` — tmux-tray issues `tmux new-session -d -s <name> [-c <cwd>] <command|path>`.
* `self-managed` — tmux-tray runs the script detached; the script manages its own tmux session (see the `james/run.sh` case).

### Conservative *Start now*
If the entry is already running (tmux session exists **or** matching PID), the button shows a warning dialog with the method and PID — no kill, no restart. You stay in control.

### Bidirectional XDG sync
On every Startup-Tmux dialog refresh (and on app startup), the registry is reconciled with the `.desktop` files:
* Missing `.desktop` → regenerated from the TOML.
* `.desktop` `Hidden=true` disagrees with TOML `enabled=true` → TOML flipped to match (KDE toggle wins).
* `.desktop` we own but no TOML entry → removed as orphan.

---

## 🔬 Debugging

```bash
uv run tmux-tray --debug
# or: TMUX_TRAY_DEBUG=1 uv run tmux-tray
```

Enables DEBUG-level Python logging *and* forwards every Qt message
(`qInstallMessageHandler`) to stderr with source file/line. Useful when
the tray menu, icon resolution, or autostart sync misbehaves.

`Ctrl+C` is honoured even while the Qt event loop is running.

---

## 🗂️ Project Layout

```
src/tmux_tray/
├── __main__.py                 # CLI: tmux-tray | --start <id> | --debug
├── config.py                   # XDG path helpers
├── state.py                    # in-memory per-session state cache
├── notify.py                   # tray QSystemTrayIcon notification helper
├── tmux/
│   ├── socket.py               # socket discovery + tmux_exec (2s timeout)
│   ├── sessions.py             # list/has/attach/kill helpers
│   ├── capture.py              # `capture-pane` for hover tooltip
│   ├── process.py              # pane PID + process-tree kill
│   └── restart.py              # safe respawn / re-create session
├── startup/
│   ├── registry.py             # Entry dataclass + TOML CRUD (atomic writes)
│   ├── naming.py               # slugify, derive_name_and_id, suggest_command
│   ├── detection.py            # is_self_tmux, find_running_pids, scan_xdg_autostart
│   ├── xdg.py                  # generate/remove ~/.config/autostart/*.desktop
│   ├── runner.py               # mode-aware executor + conservative running check
│   └── sync.py                 # reconcile TOML ↔ XDG (bidirectional)
├── ui/
│   ├── tray.py                 # TmuxTray (QSystemTrayIcon) + right-click menu
│   ├── startup_dialog.py       # the Startup-Tmux QDialog
│   ├── add_wizard.py           # Add/Edit entry wizard
│   └── resources.py            # app_icon() / system_desktop_file_installed()
└── assets/
    ├── icons/tmux-tray.svg
    └── tmux-tray.desktop

packaging/
├── PKGBUILD                    # Arch
└── build-packages.sh           # fpm-based .deb and .rpm builder

tests/                          # pytest (100+ tests, Qt-free)
```

---

## 💡 Tips

* **GNOME**: install the *AppIndicator and KStatusNotifierItem* extension if the tray icon doesn't show.
* **Logs in autostart**: redirect stdout/stderr in your `.desktop` `Exec=` for offline diagnostics.
* **Custom terminal**: Konsole is hardcoded today; patches welcome to make it XDG default-handler driven.
* **Per-session restart safety**: the restart action captures the current cwd/cmd via tmux's `pane_current_path` / `pane_start_command` before sending `Ctrl-C`; if the tmux server died entirely, the session is re-created with the saved state.

---

## 🧑‍💻 Author

Developed by **Walter Rodrigues**.

---

## 🧱 License

Released under the [MIT License](LICENSE).

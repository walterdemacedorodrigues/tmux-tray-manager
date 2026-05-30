# 🧰 Tmux Tray — System Tray Monitor for Tmux Sessions

Tmux Tray is a lightweight Python + Qt6 application that sits quietly in your system tray and provides a dynamic overview of your running **tmux** sessions. It lets you attach, restart, and kill sessions directly from the tray — no need to open the terminal manually.

---

## ✨ Features

* ✅ **Live session list** — detects all tmux sessions dynamically in real time.
* 🖱️ **Tray-based control** — open, restart, or kill sessions with a simple click.
* 💬 **Hover preview** — shows the last line of the active pane in the selected session.
* ⚙️ **Selectable focus** — choose which session the tooltip follows (✓ mark selector).
* 🖥️ **Autostart support** — automatically starts with your desktop session.
* 🔄 **Cross-desktop compatible** — designed for KDE Plasma 6 (Wayland) but works elsewhere.
* 🧩 **Lightweight** — no background daemons, no bloat.

---

## 🧭 Compatibility Table

| Component               | Minimum Requirement                           | Tested On                          | Notes                                           |
| ----------------------- | --------------------------------------------- | ---------------------------------- | ----------------------------------------------- |
| **OS**                  | Linux (Arch, Debian, Fedora, openSUSE, macOS) | ✅ Garuda Linux KDE Plasma 6        | Native Qt tray works best on KDE                |
| **Desktop Environment** | KDE Plasma / GNOME / XFCE                     | ✅ KDE, ⚠️ GNOME requires extension | GNOME users need *AppIndicator* extension       |
| **Session Type**        | X11 or Wayland                                | ✅ Wayland                          | Full support for KDE’s StatusNotifierItem (SNI) |
| **Dependencies**        | Python ≥ 3.8, PySide6, tmux                   | ✅ Python 3.13, PySide6 6.7+        | Automatically installed by the installer        |
| **Terminal Emulator**   | Konsole (preferred), Kitty, Alacritty, XTerm  | ✅ Konsole                          | Auto-detected and patched during install        |

---

## ⚙️ Installation

### Arch / Manjaro / Garuda

```bash
cd packaging
makepkg -si        # builds and installs from PKGBUILD
```

### Debian / Ubuntu / Mint, Fedora / openSUSE / RHEL

Requires `fpm` (Ruby gem) and `uv` on the build host:

```bash
gem install --user-install fpm   # if you don't have it
./packaging/build-packages.sh    # produces dist/*.deb and dist/*.rpm
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

> **Note (dev mode):** without a system install the taskbar icon falls
> back to the Wayland generic icon — KDE Plasma needs the `.desktop`
> in `/usr/share/applications/` to resolve the icon via `app_id`.
> The window decoration icon still uses our bundled SVG.

---

## 🧩 How It Works

1. The app queries `tmux ls` every 2 seconds.
2. It updates the tray icon dynamically:

   * 🟢 **Green** → one or more sessions running.
   * 🔴 **Red** → no sessions detected.
3. Hovering shows the log of the selected session.
4. Double-click opens the selected session in a terminal.
5. Each session has a submenu:

   * `open` → attach in terminal.
   * `restart` → re-run the last command.
   * `kill` → terminate the session.

---

## 💡 Tips

* **GNOME Users**: install the *AppIndicator* extension if the tray icon doesn’t show.
* **Logs**: redirect stdout/stderr in your autostart entry to `~/.local/share/tmux-tray.log` for diagnostics.

---

## 🧑‍💻 Author

Developed by **Walter Rodrigues**.


---

## 🧱 License


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

## ⚙️ Installation Guide

### 1️⃣ Clone or Download

```bash
git clone https://github.com/yourusername/tmux-tray.git
cd tmux-tray
```

### 2️⃣ Run the Installer

```bash
chmod +x install_tmux_tray.sh
./install_tmux_tray.sh
```

This script:

* Installs **tmux**, **Python**, and **PySide6** automatically.
* Copies the app to `~/.local/bin/tmux-tray.py`.
* Creates autostart and desktop launcher entries.
* Detects your terminal emulator (Konsole, Kitty, Alacritty, etc).

### 3️⃣ Start the App

```bash
~/.local/bin/tmux-tray.py &
```

Or simply log out and log back in — it’ll start automatically.

---

## 🧩 How It Works

1. The app queries `tmux ls` every 2 seconds.
2. It updates the tray icon dynamically:

   * 🟢 **Green** → one or more sessions running.
   * 🔴 **Red** → no sessions detected.
3. Hovering shows the **last line** of the selected session.
4. Double-click opens the selected session in a terminal.
5. Each session has a submenu:

   * `open` → attach in terminal.
   * `restart` → re-run the last command.
   * `kill` → terminate the session.

---

## 🧰 Manual Startup Configuration

If you ever need to recreate the autostart file manually:

`~/.config/autostart/tmux-tray.desktop`

```ini
[Desktop Entry]
Type=Application
Name=Tmux Tray
Exec=/home/blackbloc/.local/bin/tmux-tray.py
Icon=utilities-terminal
Terminal=false
X-GNOME-Autostart-enabled=true
```

---

## 💡 Tips

* **GNOME Users**: install the *AppIndicator* extension if the tray icon doesn’t show.
* **Custom Terminal**: modify the launcher in `~/.local/bin/tmux-tray.py` if you want a different terminal.
* **Logs**: to enable logging, edit the autostart file:

  ```ini
  Exec=/home/blackbloc/.local/bin/tmux-tray.py >> ~/.local/share/tmux-tray.log 2>&1
  ```
* **AppImage build**: you can build a self-contained AppImage with:

  ```bash
  ./install_tmux_tray.sh --appimage
  ```

---

## 🧑‍💻 Author

Developed by **Walter Rodrigues**.


---

## 🧱 License


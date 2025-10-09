#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Tmux Tray"
BIN_NAME="tmux-tray.py"                         # <— seu arquivo
INSTALL_BIN="$HOME/.local/bin/$BIN_NAME"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
DESKTOP_FILE_AUTOSTART="$AUTOSTART_DIR/tmux-tray.desktop"
DESKTOP_DIR="${XDG_DESKTOP_DIR:-$HOME/Desktop}"
DESKTOP_FILE_SHORTCUT="$DESKTOP_DIR/Tmux Tray.desktop"
PYTHON_BIN="${PYTHON_BIN:-python3}"

info()  { echo -e "\033[1;34m[INFO]\033[0m $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m $*"; }
error() { echo -e "\033[1;31m[ERROR]\033[0m $*"; }

detect_pkgmgr() {
  if command -v pacman >/dev/null 2>&1; then echo pacman
  elif command -v apt-get >/dev/null 2>&1; then echo apt
  elif command -v dnf >/dev/null 2>&1; then echo dnf
  elif command -v zypper >/dev/null 2>&1; then echo zypper
  elif [[ "$(uname -s)" == "Darwin" ]] && command -v brew >/dev/null 2>&1; then echo brew
  else echo unknown; fi
}

ensure_dir() { mkdir -p "$1"; }

install_tmux() {
  case "$PKG" in
    pacman) sudo pacman -S --needed --noconfirm tmux ;;
    apt)    sudo apt-get update && sudo apt-get install -y tmux ;;
    dnf)    sudo dnf install -y tmux ;;
    zypper) sudo zypper install -y tmux ;;
    brew)   brew install tmux ;;
    *)      warn "Unknown pkg manager: install 'tmux' manually."; return 1 ;;
  esac
}

install_python_and_pyside6() {
  case "$PKG" in
    pacman) sudo pacman -S --needed --noconfirm python python-pip python-pyside6 || true ;;
    apt)    sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-pyside6.qt6 || true ;;
    dnf)    sudo dnf install -y python3 python3-pip python3-qt5 qt6-qtbase-devel || true ;;
    zypper) sudo zypper install -y python3 python3-pip python3-qt6 || true ;;
    brew)   brew install python@3 pyside ;;
    *)      warn "Will try pip for PySide6."; ;;
  esac
  if ! $PYTHON_BIN -c "import PySide6" >/dev/null 2>&1; then
    $PYTHON_BIN -m pip install --user --upgrade pip
    $PYTHON_BIN -m pip install --user PySide6
  fi
  if ! $PYTHON_BIN -c "import PySide6" >/dev/null 2>&1; then
    error "PySide6 not importable after installation."; exit 1
  fi
}

detect_terminal() {
  if command -v konsole >/dev/null 2>&1; then echo konsole
  elif command -v kitty >/dev/null 2>&1; then echo kitty
  elif command -v alacritty >/dev/null 2>&1; then echo alacritty
  elif command -v gnome-terminal >/dev/null 2>&1; then echo gnome-terminal
  elif command -v xterm >/dev/null 2>&1; then echo xterm
  else echo ""; fi
}

check_desktop_env() {
  local desktop="${XDG_CURRENT_DESKTOP:-unknown}"
  info "Desktop: $desktop"
  if [[ "$desktop" == *KDE* ]]; then
    info "KDE detected — QSystemTrayIcon/SNI supported."
  elif [[ "$desktop" == *GNOME* ]]; then
    warn "GNOME detected. If tray icon is missing, install AppIndicator/KStatusNotifierItem extension."
  else
    warn "Unknown desktop. If tray does not show, SNI might be unsupported."
  fi
}

install_binary() {
  ensure_dir "$HOME/.local/bin"
  if [[ ! -f "./$BIN_NAME" ]]; then
    error "Cannot find './$BIN_NAME'. Run this installer from the folder containing it."; exit 1
  fi
  local term=$(detect_terminal)
  if [[ -z "$term" ]]; then
    warn "No terminal emulator found. Double-click/open may not work."
    cp "./$BIN_NAME" "$INSTALL_BIN"
  else
    info "Using terminal: $term"
    # Replace 'konsole -e' with detected terminal if needed
    if [[ "$term" != "konsole" ]]; then
      sed -E 's/konsole -e/'"$term"' -e/g' "./$BIN_NAME" > "$INSTALL_BIN"
    else
      cp "./$BIN_NAME" "$INSTALL_BIN"
    fi
  fi
  chmod +x "$INSTALL_BIN"
}

create_desktop_entries() {
  ensure_dir "$AUTOSTART_DIR"
  cat > "$DESKTOP_FILE_AUTOSTART" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME
Comment=System tray monitor for tmux sessions
Exec=$INSTALL_BIN
Icon=utilities-terminal
Terminal=false
Categories=Utility;System;
StartupNotify=false
X-GNOME-Autostart-enabled=true
NoDisplay=false
EOF
  chmod +x "$DESKTOP_FILE_AUTOSTART"
  info "Autostart: $DESKTOP_FILE_AUTOSTART"

  ensure_dir "$DESKTOP_DIR"
  cat > "$DESKTOP_FILE_SHORTCUT" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME
Comment=System tray monitor for tmux sessions
Exec=$INSTALL_BIN
Icon=utilities-terminal
Terminal=false
Categories=Utility;System;
StartupNotify=false
EOF
  chmod +x "$DESKTOP_FILE_SHORTCUT"
  info "Desktop shortcut: $DESKTOP_FILE_SHORTCUT"
}

main() {
  info "Installing $APP_NAME ..."
  PKG=$(detect_pkgmgr)
  info "Pkg manager: $PKG"
  check_desktop_env
  install_tmux || true
  install_python_and_pyside6
  install_binary
  create_desktop_entries
  info "Done."
  echo
  echo "Start now: $INSTALL_BIN &"
  echo "Autostart is ready — re-login to see the tray automatically."
}

main "$@"

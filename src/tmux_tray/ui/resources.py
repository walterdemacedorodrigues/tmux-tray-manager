"""Locate bundled resources (icon) at runtime.

The SVG ships inside the package (src/tmux_tray/assets/icons/) so it's
available whether the project was installed system-wide or via uv pip.
"""

import os
from pathlib import Path
from typing import Optional

from PySide6.QtGui import QIcon

import tmux_tray

_PACKAGE_DIR = Path(tmux_tray.__file__).parent
_ICON_FILE = _PACKAGE_DIR / "assets" / "icons" / "tmux-tray.svg"

_cached_icon: Optional[QIcon] = None


def app_icon_path() -> Optional[Path]:
    return _ICON_FILE if _ICON_FILE.is_file() else None


def app_icon() -> QIcon:
    """Return the tmux-tray QIcon (cached). Empty QIcon if file missing."""
    global _cached_icon
    if _cached_icon is None:
        p = app_icon_path()
        _cached_icon = QIcon(str(p)) if p else QIcon()
    return _cached_icon


def system_desktop_file_installed() -> bool:
    """True if tmux-tray.desktop exists in an XDG applications directory.

    Used to decide whether to call QApplication.setDesktopFileName: doing so
    when the file is missing makes xdg-desktop-portal emit a noisy
    "App info not found" warning (dev mode via `uv run`).
    """
    name = "tmux-tray.desktop"
    candidates = [
        Path.home() / ".local" / "share" / "applications" / name,
        Path("/usr/local/share/applications") / name,
        Path("/usr/share/applications") / name,
    ]
    for raw in os.environ.get("XDG_DATA_DIRS", "").split(":"):
        if raw:
            candidates.append(Path(raw) / "applications" / name)
    for raw in os.environ.get("XDG_DATA_HOME", "").split(":"):
        if raw:
            candidates.append(Path(raw) / "applications" / name)
    return any(c.is_file() for c in candidates)


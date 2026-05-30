"""XDG autostart .desktop generation for Startup Tmux entries.

Each enabled entry gets ``~/.config/autostart/tmux-tray-startup-<slug>.desktop``
that calls ``tmux-tray --start <slug>``. The runner picks the right execution
mode based on the TOML registry.
"""

from pathlib import Path
from typing import Optional

from tmux_tray.config import autostart_dir, ensure_autostart_dir
from tmux_tray.startup.registry import Entry

DESKTOP_PREFIX = "tmux-tray-startup-"


def desktop_file_path(slug: str, autostart_root: Optional[Path] = None) -> Path:
    root = autostart_root if autostart_root is not None else autostart_dir()
    return root / f"{DESKTOP_PREFIX}{slug}.desktop"


def _escape_desktop_value(s: str) -> str:
    return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t")


def render_desktop(entry: Entry) -> str:
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        "Version=1.0",
        f"Name={_escape_desktop_value(entry.name)}",
        "Comment=Auto-started via tmux-tray",
        f"Exec=tmux-tray --start {entry.slug}",
        "Icon=tmux-tray",
        "Terminal=false",
        "Categories=Utility;System;",
        "StartupNotify=false",
        "X-GNOME-Autostart-enabled=true",
        "NoDisplay=false",
        f"Hidden={'true' if not entry.enabled else 'false'}",
        f"X-TmuxTray-Slug={entry.slug}",
    ]
    return "\n".join(lines) + "\n"


def write_desktop_file(entry: Entry, autostart_root: Optional[Path] = None) -> Path:
    if autostart_root is not None:
        autostart_root.mkdir(parents=True, exist_ok=True)
    else:
        ensure_autostart_dir()
    p = desktop_file_path(entry.slug, autostart_root)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(render_desktop(entry), encoding="utf-8")
    tmp.chmod(0o755)
    tmp.replace(p)
    return p


def remove_desktop_file(slug: str, autostart_root: Optional[Path] = None) -> bool:
    p = desktop_file_path(slug, autostart_root)
    if not p.exists():
        return False
    p.unlink()
    return True


def _read_kv(content: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def is_hidden(slug: str, autostart_root: Optional[Path] = None) -> Optional[bool]:
    """Return True/False if Hidden is set in our .desktop, None if no file."""
    p = desktop_file_path(slug, autostart_root)
    if not p.exists():
        return None
    try:
        kv = _read_kv(p.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    val = kv.get("Hidden", "false").strip().lower()
    return val == "true"


def list_managed_slugs(autostart_root: Optional[Path] = None) -> list[str]:
    """Return slugs of all .desktop files we own in the autostart dir."""
    root = autostart_root if autostart_root is not None else autostart_dir()
    if not root.is_dir():
        return []
    slugs: list[str] = []
    for f in sorted(root.glob(f"{DESKTOP_PREFIX}*.desktop")):
        name = f.name[len(DESKTOP_PREFIX):-len(".desktop")]
        if name:
            slugs.append(name)
    return slugs

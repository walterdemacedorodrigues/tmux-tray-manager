"""Storage layer for Startup Tmux entries.

Persists entries to ``~/.config/tmux-tray/startup.toml`` (XDG).
Hand-rolled TOML emitter keeps the schema readable and avoids an extra dep.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Optional

from tmux_tray.config import ensure_config_dir, startup_toml_path

Mode = Literal["tmux-wrapped", "self-managed"]
_VALID_MODES = ("tmux-wrapped", "self-managed")
_FIELD_ORDER = (
    "slug", "name", "path", "command", "cwd", "mode", "session_name", "enabled",
)


@dataclass
class Entry:
    slug: str
    name: str
    path: str
    session_name: str
    mode: Mode = "tmux-wrapped"
    cwd: Optional[str] = None
    enabled: bool = True
    command: Optional[str] = None
    """Optional command-line override.

    If set, the runner executes this command instead of running ``path``
    directly. Lets users invoke interpreters (e.g. ``python3 start.py``)
    or pass extra arguments. ``path`` is still the canonical script
    location used for detection.
    """

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Entry":
        mode = d.get("mode", "tmux-wrapped")
        if mode not in _VALID_MODES:
            raise ValueError(f"Invalid mode '{mode}' for entry '{d.get('slug', '?')}'")
        return cls(
            slug=d["slug"],
            name=d["name"],
            path=d["path"],
            session_name=d["session_name"],
            mode=mode,
            cwd=d.get("cwd"),
            enabled=bool(d.get("enabled", True)),
            command=d.get("command"),
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "slug": self.slug,
            "name": self.name,
            "path": self.path,
            "mode": self.mode,
            "session_name": self.session_name,
            "enabled": self.enabled,
        }
        if self.cwd:
            d["cwd"] = self.cwd
        if self.command:
            d["command"] = self.command
        return d


def _escape_toml_basic_string(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _emit_value(val: Any) -> str:
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, str):
        return f'"{_escape_toml_basic_string(val)}"'
    raise TypeError(f"Unsupported TOML value type: {type(val).__name__}")


def _emit_entry(e: Entry) -> str:
    d = e.to_dict()
    lines = ["[[entry]]"]
    for key in _FIELD_ORDER:
        if key not in d:
            continue
        lines.append(f"{key} = {_emit_value(d[key])}")
    return "\n".join(lines)


def _resolve(path: Optional[Path]) -> Path:
    return path if path is not None else startup_toml_path()


def load_entries(path: Optional[Path] = None) -> list[Entry]:
    p = _resolve(path)
    if not p.exists():
        return []
    try:
        with open(p, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError:
        return []
    out: list[Entry] = []
    for raw in data.get("entry", []) or []:
        try:
            out.append(Entry.from_dict(raw))
        except (KeyError, ValueError):
            continue
    return out


def save_entries(entries: list[Entry], path: Optional[Path] = None) -> None:
    p = _resolve(path)
    if path is None:
        ensure_config_dir()
    else:
        p.parent.mkdir(parents=True, exist_ok=True)
    body = "\n\n".join(_emit_entry(e) for e in entries)
    if body:
        body += "\n"
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(p)


def find_entry(slug: str, path: Optional[Path] = None) -> Optional[Entry]:
    for e in load_entries(path):
        if e.slug == slug:
            return e
    return None


def add_entry(entry: Entry, path: Optional[Path] = None) -> None:
    entries = load_entries(path)
    if any(e.slug == entry.slug for e in entries):
        raise ValueError(f"Entry with slug '{entry.slug}' already exists")
    entries.append(entry)
    save_entries(entries, path)


def remove_entry(slug: str, path: Optional[Path] = None) -> bool:
    entries = load_entries(path)
    new = [e for e in entries if e.slug != slug]
    if len(new) == len(entries):
        return False
    save_entries(new, path)
    return True


def update_entry(slug: str, path: Optional[Path] = None, **updates: Any) -> Optional[Entry]:
    entries = load_entries(path)
    target: Optional[Entry] = None
    for e in entries:
        if e.slug == slug:
            target = e
            break
    if target is None:
        return None
    for k, v in updates.items():
        if not hasattr(target, k):
            raise AttributeError(f"Entry has no field '{k}'")
        setattr(target, k, v)
    if target.mode not in _VALID_MODES:
        raise ValueError(f"Invalid mode '{target.mode}'")
    save_entries(entries, path)
    return target

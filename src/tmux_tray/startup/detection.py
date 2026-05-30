"""Detection heuristics for the 3 redundancy checks.

1. is_self_tmux  — static grep on script content
2. find_running_pids  — scan /proc/*/cmdline for the script path
3. scan_xdg_autostart  — find .desktop files referencing the script

All functions are pure (no side effects) and take injectable paths
for testability.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from tmux_tray.config import autostart_dir

_SELF_TMUX_RE = re.compile(
    r"\btmux\s+(new-session|new\b|attach\b|a\b|has-session\b|switch-client\b|kill-session\b)"
    r"|\bexec\s+tmux\b",
)

_MAX_SCRIPT_BYTES = 1 << 20  # 1 MiB; scripts larger than this are likely not shell scripts


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    cmdline: list[str] = field(default_factory=list)
    matched_arg: str = ""


def is_self_tmux(path: Path | str) -> bool:
    """Return True if the script appears to manage its own tmux session.

    Heuristic regex over the file's text. Returns False for binaries,
    missing files, and files that can't be decoded.
    """
    p = Path(path)
    try:
        size = p.stat().st_size
    except OSError:
        return False
    if size > _MAX_SCRIPT_BYTES:
        return False
    try:
        data = p.read_bytes()
    except OSError:
        return False
    if b"\x00" in data[:4096]:
        return False
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = data.decode("latin-1")
        except UnicodeDecodeError:
            return False
    return _SELF_TMUX_RE.search(text) is not None


def find_running_pids(target_path: str, proc_root: Path = Path("/proc")) -> list[ProcessInfo]:
    """Find PIDs whose cmdline contains the given script path.

    Matches either by literal equality or by resolved realpath.
    Skips PIDs we can't read (permission, race with exit).
    """
    try:
        target_real = os.path.realpath(target_path)
    except OSError:
        target_real = target_path

    found: list[ProcessInfo] = []
    if not proc_root.is_dir():
        return found

    for pid_dir in proc_root.iterdir():
        if not pid_dir.name.isdigit():
            continue
        try:
            cmdline_bytes = (pid_dir / "cmdline").read_bytes()
        except (FileNotFoundError, PermissionError, NotADirectoryError, OSError):
            continue
        if not cmdline_bytes:
            continue
        raw_args = cmdline_bytes.split(b"\x00")
        args = [a.decode("utf-8", errors="replace") for a in raw_args if a]
        if not args:
            continue
        matched: Optional[str] = None
        for a in args:
            if a == target_path:
                matched = a
                break
            try:
                if os.path.realpath(a) == target_real:
                    matched = a
                    break
            except OSError:
                continue
        if matched is not None:
            try:
                pid = int(pid_dir.name)
            except ValueError:
                continue
            found.append(ProcessInfo(pid=pid, cmdline=args, matched_arg=matched))
    return found


def scan_xdg_autostart(target_path: str, autostart_root: Optional[Path] = None) -> list[Path]:
    """List .desktop files in the XDG autostart dir whose Exec= references target_path.

    Substring match on the value of Exec=. Good enough for v1.
    """
    root = autostart_root if autostart_root is not None else autostart_dir()
    matches: list[Path] = []
    if not root.is_dir():
        return matches
    for f in sorted(root.glob("*.desktop")):
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for raw in content.splitlines():
            line = raw.strip()
            if line.startswith("Exec=") and target_path in line[len("Exec="):]:
                matches.append(f)
                break
    return matches

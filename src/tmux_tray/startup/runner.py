"""Execution layer for Startup Tmux entries.

Invoked by:
  - The autostart .desktop on login (tmux-tray --start <slug>)
  - The UI's "Start now" button

Conservative semantics: never duplicates a running process. If a matching
session or PID is already alive, prints a warning and exits 0.
"""

import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Optional

from tmux_tray.startup.detection import ProcessInfo, find_running_pids
from tmux_tray.startup.registry import Entry, find_entry
from tmux_tray.tmux.sessions import session_exists
from tmux_tray.tmux.socket import tmux_run


@dataclass(frozen=True)
class RunningInfo:
    method: str
    details: str
    pids: tuple[ProcessInfo, ...] = ()


def detect_running(entry: Entry) -> Optional[RunningInfo]:
    if session_exists(entry.session_name):
        return RunningInfo(method="tmux-session", details=f"tmux session '{entry.session_name}' exists")
    pids = find_running_pids(entry.path)
    if pids:
        details = f"PID {pids[0].pid} matched '{pids[0].matched_arg}'"
        return RunningInfo(method="process", details=details, pids=tuple(pids))
    return None


def _exec_self_managed(entry: Entry) -> int:
    try:
        subprocess.Popen(
            [entry.path],
            cwd=entry.cwd or None,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return 0
    except OSError as e:
        print(f"tmux-tray: failed to spawn '{entry.path}': {e}", file=sys.stderr)
        return 1


def _exec_tmux_wrapped(entry: Entry) -> int:
    args = ["new-session", "-d", "-s", entry.session_name]
    if entry.cwd:
        args += ["-c", entry.cwd]
    args.append(entry.path)
    rc, _, err, _ = tmux_run(args)
    if rc != 0:
        print(f"tmux-tray: tmux new-session failed for '{entry.slug}': {err}", file=sys.stderr)
        return 1
    return 0


def execute_entry(entry: Entry) -> int:
    if entry.mode == "self-managed":
        return _exec_self_managed(entry)
    if entry.mode == "tmux-wrapped":
        return _exec_tmux_wrapped(entry)
    print(f"tmux-tray: unknown mode '{entry.mode}' for entry '{entry.slug}'", file=sys.stderr)
    return 1


def start_by_slug(
    slug: str,
    *,
    lookup: Callable[[str], Optional[Entry]] = find_entry,
    detector: Callable[[Entry], Optional[RunningInfo]] = detect_running,
    executor: Callable[[Entry], int] = execute_entry,
) -> int:
    entry = lookup(slug)
    if entry is None:
        print(f"tmux-tray: no startup entry with slug '{slug}'", file=sys.stderr)
        return 2
    if not entry.enabled:
        print(f"tmux-tray: entry '{slug}' is disabled; skipping", file=sys.stderr)
        return 0
    already = detector(entry)
    if already is not None:
        print(
            f"tmux-tray: entry '{slug}' already running ({already.details}); skipping",
            file=sys.stderr,
        )
        return 0
    return executor(entry)

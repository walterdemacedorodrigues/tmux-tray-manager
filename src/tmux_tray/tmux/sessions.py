import os
import shlex
from typing import List, Optional

from tmux_tray.tmux.socket import get_active_socket, tmux_out, tmux_run


def tmux_server_running() -> bool:
    rc, _, _, _ = tmux_out(["list-sessions"])
    return rc == 0


def session_exists(session: str) -> bool:
    rc, _, _, _ = tmux_out(["has-session", "-t", session])
    return rc == 0


def list_sessions() -> List[str]:
    rc, stdout, _, _ = tmux_out(["list-sessions", "-F", "#{session_name}"])
    if rc != 0 or not stdout:
        return []
    return [ln.strip() for ln in stdout.splitlines() if ln.strip()]


def most_recent_session() -> Optional[str]:
    rc, stdout, _, _ = tmux_out(["list-sessions", "-F", "#{session_name} #{session_last_attached}"])
    if rc != 0 or not stdout:
        return None
    best_name, best_ts = None, -1
    for line in stdout.splitlines():
        try:
            name, ts = line.rsplit(" ", 1)
            ts = int(ts)
        except Exception:
            name, ts = line.strip(), -1
        if ts > best_ts:
            best_name, best_ts = name.strip(), ts
    if best_name:
        return best_name
    s = list_sessions()
    return s[0] if s else None


def attach(session: str) -> None:
    sock = get_active_socket()
    base = ["tmux"]
    if sock:
        base += ["-S", sock]
    cmd = " ".join([shlex.quote(x) for x in (["konsole", "-e"] + base + ["attach", "-t", session])]) + " &"
    os.system(cmd)


def kill_session(session: str) -> None:
    tmux_run(["kill-session", "-t", session])


def open_blank_terminal() -> None:
    sock = get_active_socket()
    base = ["tmux"]
    if sock:
        base += ["-S", sock]
    cmd = " ".join([shlex.quote(x) for x in (["konsole", "-e"] + base)]) + " &"
    os.system(cmd)

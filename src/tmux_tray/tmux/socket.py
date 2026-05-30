import os
import subprocess
from typing import List, Optional, Tuple

TMUX_SOCKET: Optional[str] = None
TMUX_CMD_TIMEOUT_SEC = 2.0


def _parse_tmux_env(val: str) -> Optional[str]:
    if not val:
        return None
    return val.split(",")[0] if "," in val else val


def _list_tmp_sockets() -> List[str]:
    base = f"/tmp/tmux-{os.getuid()}"
    if not os.path.isdir(base):
        return []
    cands = []
    for fn in os.listdir(base):
        p = os.path.join(base, fn)
        if os.path.exists(p):
            cands.append(p)
    cands.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return cands


def tmux_candidates() -> List[Optional[str]]:
    cands: List[Optional[str]] = []
    if TMUX_SOCKET:
        cands.append(TMUX_SOCKET)
    env_sock = _parse_tmux_env(os.environ.get("TMUX", ""))
    if env_sock and env_sock not in cands:
        cands.append(env_sock)
    for s in _list_tmp_sockets():
        if s not in cands:
            cands.append(s)
    if None not in cands:
        cands.append(None)
    return cands


def _tmux_cmd_list(sock: Optional[str], args: List[str]) -> List[str]:
    base = ["tmux"]
    if sock:
        base += ["-S", sock]
    return base + args


def tmux_exec(args: List[str]) -> Tuple[int, str, str, Optional[str]]:
    """Try multiple sockets; return (rc, stdout, stderr, socket_used).

    Each candidate is given TMUX_CMD_TIMEOUT_SEC before we move on, so a
    stuck tmux server or stale socket can never block the Qt event loop.
    """
    global TMUX_SOCKET
    last = (1, "", "no tmux socket responded", None)
    for sock in tmux_candidates():
        cmd = _tmux_cmd_list(sock, args)
        try:
            p = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=TMUX_CMD_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            last = (1, "", f"timeout after {TMUX_CMD_TIMEOUT_SEC}s", sock)
            continue
        except Exception as e:
            last = (1, "", str(e), sock)
            continue
        rc = p.returncode
        out = (p.stdout or "").strip()
        err = (p.stderr or "").strip()
        if rc == 0:
            if sock != TMUX_SOCKET:
                TMUX_SOCKET = sock
            return rc, out, err, sock
        last = (rc, out, err, sock)
    return last


def tmux_out(args: List[str]) -> Tuple[int, str, str, Optional[str]]:
    return tmux_exec(args)


def tmux_run(args: List[str]) -> Tuple[int, str, str, Optional[str]]:
    return tmux_exec(args)


def get_active_socket() -> Optional[str]:
    return TMUX_SOCKET


def clean_tmux_string(s: str) -> str:
    """Remove aspas extras que o tmux adiciona em alguns formatos."""
    if not s:
        return s
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    s = s.replace('\\"', '"')
    return s

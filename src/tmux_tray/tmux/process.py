import os
import signal
import subprocess
import time
from typing import Optional

from tmux_tray.state import get_state
from tmux_tray.tmux.socket import clean_tmux_string, tmux_out

SHELLS = {"sh", "bash", "zsh", "fish", "dash", "-bash", "-zsh", "-fish"}


def pane_pid(session: str) -> Optional[int]:
    rc, stdout, _, _ = tmux_out(["display", "-p", "-t", session, "#{pane_pid}"])
    if rc != 0:
        return None
    try:
        pid = int(stdout.strip())
        return pid if pid > 0 else None
    except Exception:
        return None


def group_has_members(pgid: int) -> bool:
    try:
        r = subprocess.run(["ps", "-o", "pid=", "-g", str(pgid)], capture_output=True, text=True, timeout=2)
        return bool(r.stdout.strip())
    except Exception:
        return False


def kill_process_tree(pid: int) -> None:
    try:
        subprocess.run(["pkill", "-TERM", "-P", str(pid)], timeout=2)
        time.sleep(0.5)
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        time.sleep(1.0)
        try:
            pgid = os.getpgid(pid)
        except Exception:
            pgid = None
        if pgid and group_has_members(pgid):
            subprocess.run(["pkill", "-KILL", "-g", str(pgid)], timeout=2)
            time.sleep(0.3)
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    except Exception:
        pass


def get_running_command(session: str) -> Optional[str]:
    pid = pane_pid(session)
    if not pid:
        return None
    try:
        result = subprocess.run(
            ["ps", "--ppid", str(pid), "-o", "pid=,cmd="],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode != 0:
            return None
        lines = result.stdout.strip().split("\n")
        if not lines:
            return None
        for line in lines:
            parts = line.strip().split(None, 1)
            if len(parts) < 2:
                continue
            cmd = parts[1]
            cmd_base = os.path.basename(cmd.split()[0])
            if cmd_base not in SHELLS:
                return cmd
        return None
    except Exception:
        return None


def collect_session_state(session: str) -> None:
    rc_cwd, cwd, _, _ = tmux_out(["display", "-p", "-t", session, "#{pane_current_path}"])
    running_cmd = get_running_command(session)

    if not running_cmd:
        rc_cmd, cmd, _, _ = tmux_out(["display", "-p", "-t", session, "#{pane_start_command}"])
        if rc_cmd == 0 and cmd:
            cmd = clean_tmux_string(cmd)
            running_cmd = cmd if cmd else None

    if rc_cwd == 0 or running_cmd:
        st = get_state(session)
        changed = False
        if rc_cwd == 0 and cwd and cwd != st.get("cwd"):
            st["cwd"] = cwd
            changed = True
        if running_cmd and running_cmd != st.get("cmd"):
            cmd_base = os.path.basename(running_cmd.split()[0])
            if cmd_base not in SHELLS:
                st["cmd"] = running_cmd
                changed = True
        if changed:
            st["ts"] = time.time()


def collect_all_sessions_state() -> None:
    from tmux_tray.tmux.sessions import list_sessions
    for s in list_sessions():
        collect_session_state(s)

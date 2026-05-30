import os
import signal
import time
from typing import TYPE_CHECKING, Optional

from tmux_tray.notify import notify
from tmux_tray.state import get_state
from tmux_tray.tmux.process import (
    collect_session_state,
    group_has_members,
    pane_pid,
    SHELLS,
)
from tmux_tray.tmux.sessions import session_exists, tmux_server_running
from tmux_tray.tmux.socket import clean_tmux_string, tmux_run

if TYPE_CHECKING:
    from PySide6.QtWidgets import QSystemTrayIcon


def create_session(session: str, cwd: Optional[str], start_cmd: Optional[str]) -> bool:
    args = ["new-session", "-d", "-s", session]
    if cwd:
        args += ["-c", cwd]
    if start_cmd and start_cmd.strip():
        args += [start_cmd]
    rc, _, _, _ = tmux_run(args)
    return rc == 0


def restart_session(session: str, tray: "Optional[QSystemTrayIcon]" = None) -> None:
    if not tmux_server_running():
        notify(tray, "tmux tray", "No tmux server detected.", 3200)
        return
    if not session_exists(session):
        notify(tray, "tmux tray", f"Session '{session}' not found.", 3000)
        return

    collect_session_state(session)

    st = get_state(session)
    cwd_saved = st.get("cwd")
    cmd_saved = st.get("cmd")

    if not cwd_saved:
        cwd_saved = os.path.expanduser("~")

    if cmd_saved:
        cmd_saved = clean_tmux_string(cmd_saved)

    use_cmd = bool(cmd_saved) and os.path.basename(cmd_saved.split()[0]) not in SHELLS

    tmux_run(["set-option", "-w", "-t", session, "remain-on-exit", "on"])

    pid = pane_pid(session)
    rc, _, _, _ = tmux_run(["send-keys", "-t", session, "C-c"])
    if rc != 0:
        notify(tray, "tmux tray", f"Failed to send Ctrl-C to '{session}'.", 4000)
        return
    time.sleep(0.8)

    if pid:
        try:
            pgid = os.getpgid(pid)
        except Exception:
            pgid = None
        if pgid and pgid > 0:
            try:
                os.killpg(pgid, signal.SIGTERM)
                time.sleep(1.0)
                if group_has_members(pgid):
                    os.killpg(pgid, signal.SIGKILL)
                    time.sleep(0.4)
            except ProcessLookupError:
                pass

    srv_ok = tmux_server_running()
    sess_ok = session_exists(session) if srv_ok else False

    if not srv_ok or not sess_ok:
        create_session(session, cwd_saved, (cmd_saved if use_cmd else None))
        msg = f"Session '{session}' recreated"
        if cwd_saved:
            msg += f" (cwd={cwd_saved})"
        if use_cmd and cmd_saved:
            msg += f" (cmd={cmd_saved})"
        notify(tray, "tmux tray", msg, 3000)
        return

    args = ["respawn-window", "-k", "-t", session]
    if cwd_saved:
        args = ["respawn-window", "-k", "-c", cwd_saved, "-t", session]
    if use_cmd and cmd_saved:
        args.append(cmd_saved)

    rc3, _, _, _ = tmux_run(args)

    if rc3 != 0:
        ok = create_session(session, cwd_saved, (cmd_saved if use_cmd else None))
        msg = f"Respawn failed; recreated '{session}'"
        if ok:
            if cwd_saved:
                msg += f" (cwd={cwd_saved})"
            if use_cmd and cmd_saved:
                msg += f" (cmd={cmd_saved})"
            notify(tray, "tmux tray", msg, 3200)
        else:
            notify(tray, "tmux tray", f"Failed to restart '{session}'.", 4500)
        return

    msg = f"Restarted '{session}'"
    if cwd_saved:
        msg += f" (cwd={cwd_saved})"
    if use_cmd and cmd_saved:
        msg += f" (cmd={cmd_saved})"
    notify(tray, "tmux tray", msg, 2600)

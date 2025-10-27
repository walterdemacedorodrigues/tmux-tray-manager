#!/usr/bin/env python3
# tmux-tray.py — KDE/Wayland tray controller for tmux with in-memory session state
# - Dynamic session list (from tmux)
# - Per-session submenu: open / restart / kill
# - Hover selector (radio) + tooltip (last line)
# - Safe restart:
#     1) use in-memory state (cwd/cmd) collected live
#     2) send Ctrl-C; PGID cleanup (TERM->KILL)
#     3) if tmux server/session died, recreate with saved cwd/cmd; else respawn
# - Auto-detect tmux socket ($TMUX, /tmp/tmux-UID/*, default)

import sys, os, shlex, subprocess, time, signal
from typing import List, Optional, Tuple, Dict

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction, QActionGroup
from PySide6.QtCore import QTimer

# ===== in-memory state =====
# STATE[session] = {"cwd": str|None, "cmd": str|None, "ts": float}
STATE: Dict[str, Dict[str, Optional[str]]] = {}

def get_state(session: str) -> Dict[str, Optional[str]]:
    return STATE.setdefault(session, {"cwd": None, "cmd": None, "ts": time.time()})

def set_state(session: str, cwd: Optional[str], cmd: Optional[str]) -> None:
    st = get_state(session)
    if cwd: st["cwd"] = cwd
    if cmd: st["cmd"] = cmd
    st["ts"] = time.time()

# ===== tmux socket handling =====
TMUX_SOCKET: Optional[str] = None  # cache working socket

def _parse_tmux_env(val: str) -> Optional[str]:
    if not val: return None
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
    """Try multiple sockets; return (rc, stdout, stderr, socket_used)."""
    global TMUX_SOCKET
    last = (1, "", "no tmux socket responded", None)
    for sock in tmux_candidates():
        cmd = _tmux_cmd_list(sock, args)
        try:
            p = subprocess.run(cmd, capture_output=True, text=True)
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

# ===== notifications =====
def notify(tray: Optional[QSystemTrayIcon], title: str, text: str, msecs: int = 2600):
    if tray:
        try:
            tray.showMessage(title, text, QSystemTrayIcon.Information, msecs)
        except Exception:
            pass

# ===== generic shell helpers =====
def out(cmd: str) -> str:
    return subprocess.getoutput(cmd).strip()

def run(cmd: str) -> int:
    return os.system(cmd)

# ===== tmux high-level helpers =====
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
            name, ts = line.rsplit(" ", 1); ts = int(ts)
        except Exception:
            name, ts = line.strip(), -1
        if ts > best_ts:
            best_name, best_ts = name.strip(), ts
    if best_name:
        return best_name
    s = list_sessions()
    return s[0] if s else None

def attach(session: str):
    base = ["tmux"]
    if TMUX_SOCKET:
        base += ["-S", TMUX_SOCKET]
    cmd = " ".join([shlex.quote(x) for x in (["konsole","-e"] + base + ["attach","-t",session])]) + " &"
    run(cmd)

def kill_session(session: str):
    tmux_run(["kill-session", "-t", session])

def get_pane_output(session: str) -> str:
    """Captura o output visível da pane."""
    rc, stdout, _, _ = tmux_out(["capture-pane", "-p", "-t", session])
    if rc == 0 and stdout:
        return stdout
    return "(no output)"

def _pane_pid(session: str) -> Optional[int]:
    rc, stdout, _, _ = tmux_out(["display", "-p", "-t", session, "#{pane_pid}"])
    if rc != 0:
        return None
    try:
        pid = int(stdout.strip())
        return pid if pid > 0 else None
    except Exception:
        return None

def _kill_process_tree(pid: int) -> None:
    """Mata um processo e toda sua árvore de filhos recursivamente."""
    try:
        # Primeiro tenta SIGTERM em toda a árvore
        subprocess.run(["pkill", "-TERM", "-P", str(pid)], timeout=2)
        time.sleep(0.5)
        # Mata o processo principal
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        time.sleep(1.0)
        
        # Se ainda houver processos vivos, força SIGKILL
        result = subprocess.run(["pgrep", "-P", str(pid)], capture_output=True)
        if result.returncode == 0:  # Ainda há filhos vivos
            subprocess.run(["pkill", "-KILL", "-P", str(pid)], timeout=2)
            time.sleep(0.3)
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    except Exception:
        pass

# ===== string cleaning =====
def _clean_tmux_string(s: str) -> str:
    """Remove aspas extras que o tmux adiciona em alguns formatos."""
    if not s:
        return s
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    s = s.replace('\\"', '"')
    return s

# ===== live state collector =====
def _get_running_command(session: str) -> Optional[str]:
    """
    Tenta obter o comando REALMENTE em execução na pane.
    Usa ps para pegar o processo filho do tmux, não o pane_start_command.
    """
    pid = _pane_pid(session)
    if not pid:
        return None
    
    try:
        result = subprocess.run(
            ["ps", "--ppid", str(pid), "-o", "pid=,cmd="],
            capture_output=True,
            text=True,
            timeout=2
        )
        
        if result.returncode != 0:
            return None
            
        lines = result.stdout.strip().split('\n')
        if not lines:
            return None
            
        shells = {"sh", "bash", "zsh", "fish", "dash", "-bash", "-zsh", "-fish"}
        for line in lines:
            parts = line.strip().split(None, 1)
            if len(parts) < 2:
                continue
            cmd = parts[1]
            cmd_base = os.path.basename(cmd.split()[0])
            if cmd_base not in shells:
                return cmd
                
        return None
    except Exception:
        return None

def collect_session_state(session: str):
    """Refresh STATE[session] with live data from tmux."""
    rc_cwd, cwd, _, _ = tmux_out(["display", "-p", "-t", session, "#{pane_current_path}"])
    running_cmd = _get_running_command(session)
    
    if not running_cmd:
        rc_cmd, cmd, _, _ = tmux_out(["display", "-p", "-t", session, "#{pane_start_command}"])
        if rc_cmd == 0 and cmd:
            cmd = _clean_tmux_string(cmd)
            running_cmd = cmd if cmd else None
    
    if rc_cwd == 0 or running_cmd:
        st = get_state(session)
        changed = False
        
        if rc_cwd == 0 and cwd and cwd != st.get("cwd"):
            st["cwd"] = cwd
            changed = True
            
        if running_cmd and running_cmd != st.get("cmd"):
            shells = {"sh", "bash", "zsh", "fish", "dash", "-bash", "-zsh", "-fish"}
            cmd_base = os.path.basename(running_cmd.split()[0])
            if cmd_base not in shells:
                st["cmd"] = running_cmd
                changed = True
                
        if changed:
            st["ts"] = time.time()

def collect_all_sessions_state():
    for s in list_sessions():
        collect_session_state(s)

# ===== create session =====
def create_session(session: str, cwd: Optional[str], start_cmd: Optional[str]) -> bool:
    args = ["new-session", "-d", "-s", session]
    if cwd:
        args += ["-c", cwd]
    if start_cmd and start_cmd.strip():
        args += [start_cmd]
    rc, _, _, _ = tmux_run(args)
    return rc == 0

# ===== restart session =====
def restart_session(session: str, tray: Optional[QSystemTrayIcon] = None):
    """
    Safe restart usando metadados em memória:
      - Usa cwd/cmd do STATE (coletado continuamente).
      - Envia Ctrl-C; limpa PGID (TERM->KILL).
      - Se tmux server/session sumir, recria com cwd/cmd salvo.
      - Caso contrário respawn no lugar com cwd + cmd.
    """
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
        cmd_saved = _clean_tmux_string(cmd_saved)
    
    shells = {"sh", "bash", "zsh", "fish", "dash", "-bash", "-zsh", "-fish"}
    use_cmd = bool(cmd_saved) and os.path.basename(cmd_saved.split()[0]) not in shells

    tmux_run(["set-option", "-w", "-t", session, "remain-on-exit", "on"])

    pid = _pane_pid(session)
    rc, _, err, _ = tmux_run(["send-keys", "-t", session, "C-c"])
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
                if _pids_in_pgid(pgid):
                    os.killpg(pgid, signal.SIGKILL)
                    time.sleep(0.4)
            except ProcessLookupError:
                pass

    srv_ok = tmux_server_running()
    sess_ok = session_exists(session) if srv_ok else False
    
    if not srv_ok or not sess_ok:
        ok = create_session(session, cwd_saved, (cmd_saved if use_cmd else None))
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

    msg = f"Restarted '{session}' ✓"
    if cwd_saved:
        msg += f" (cwd={cwd_saved})"
    if use_cmd and cmd_saved:
        msg += f" (cmd={cmd_saved})"
    notify(tray, "tmux tray", msg, 2600)

# ===== Tray App =====
class TmuxTray:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.icon_ok    = QIcon.fromTheme("emblem-success")
        self.icon_err   = QIcon.fromTheme("emblem-error")
        self.icon_term  = QIcon.fromTheme("utilities-terminal")

        self.tray = QSystemTrayIcon(self.icon_err)
        self.tray.setToolTip("tmux: no active sessions")

        self.menu = QMenu()
        self.tray.setContextMenu(self.menu)

        self.selected_session: Optional[str] = None

        self.tray.activated.connect(self.on_activated)

        self.timer = QTimer()
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.refresh_all)

        self.refresh_all()
        self.tray.show()
        self.timer.start()

    def on_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason == QSystemTrayIcon.DoubleClick:
            sess = self.get_session_for_focus()
            if sess:
                attach(sess)
            else:
                base = ["tmux"]
                if TMUX_SOCKET:
                    base += ["-S", TMUX_SOCKET]
                cmd = " ".join([shlex.quote(x) for x in (["konsole","-e"] + base)]) + " &"
                run(cmd)

    def get_session_for_focus(self) -> Optional[str]:
        sessions = list_sessions()
        if not sessions:
            self.selected_session = None
            return None
        if self.selected_session in sessions:
            return self.selected_session
        mr = most_recent_session()
        self.selected_session = mr
        return mr

    def rebuild_menu(self):
        self.menu.clear()
        sessions = list_sessions()

        sel_menu = self.menu.addMenu("Hover session")
        group = QActionGroup(self.menu); group.setExclusive(True)
        if sessions:
            if self.selected_session not in sessions:
                self.selected_session = most_recent_session() or sessions[0]
            for s in sessions:
                act = QAction(s, self.menu)
                act.setCheckable(True)
                act.setChecked(s == self.selected_session)
                act.triggered.connect(lambda _=False, n=s: self.set_selected(n))
                group.addAction(act); sel_menu.addAction(act)
        else:
            na = QAction("(none)", self.menu); na.setEnabled(False); sel_menu.addAction(na)

        if sessions:
            self.menu.addSeparator()
            for s in sessions:
                sub = self.menu.addMenu(s)

                a_open = QAction("open", self.menu)
                a_open.triggered.connect(lambda _=False, n=s: attach(n))
                sub.addAction(a_open)

                a_restart = QAction("restart", self.menu)
                a_restart.triggered.connect(lambda _=False, n=s: restart_session(n, self.tray))
                sub.addAction(a_restart)

                a_kill = QAction("kill", self.menu)
                a_kill.triggered.connect(lambda _=False, n=s: self.kill_and_refresh(n))
                sub.addAction(a_kill)

        self.menu.addSeparator()

        quit_action = QAction("Quit", self.menu)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)

    def set_selected(self, name: str):
        self.selected_session = name
        self.refresh_tooltip_and_icon()

    def kill_and_refresh(self, name: str):
        kill_session(name)
        if self.selected_session == name:
            self.selected_session = None
        self.refresh_all()

    def refresh_tooltip_and_icon(self):
        sessions = list_sessions()
        if sessions:
            collect_all_sessions_state()

            sess = self.get_session_for_focus()
            self.tray.setIcon(self.icon_ok if sess else self.icon_err)
            if sess:
                self.tray.setToolTip(f"tmux · {sess}\n{get_pane_output(sess)}")
            else:
                    self.tray.setToolTip("tmux: no active sessions")
        else:
            self.tray.setIcon(self.icon_err)
            self.tray.setToolTip("tmux: no active sessions")

    def refresh_all(self):
        self.rebuild_menu()
        self.refresh_tooltip_and_icon()

    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    TmuxTray().run()

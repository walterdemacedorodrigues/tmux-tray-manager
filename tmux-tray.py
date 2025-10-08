#!/usr/bin/env python3
import sys, os, shlex, subprocess
from typing import List, Optional
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction, QActionGroup
from PySide6.QtCore import QTimer

# ---------- utility ----------
def run(cmd: str) -> int:
    """Execute a shell command."""
    return os.system(cmd)

def out(cmd: str) -> str:
    """Return stdout of a shell command."""
    return subprocess.getoutput(cmd).strip()

# ---------- tmux helpers ----------
def list_sessions() -> List[str]:
    """Return a list of all tmux session names."""
    txt = out('tmux list-sessions -F "#{session_name}" 2>/dev/null')
    if not txt:
        return []
    return [ln.strip() for ln in txt.splitlines() if ln.strip()]

def most_recent_session() -> Optional[str]:
    """Return the most recently attached session name."""
    txt = out('tmux list-sessions -F "#{session_name} #{session_last_attached}" 2>/dev/null')
    if not txt:
        return None
    best_name, best_ts = None, -1
    for line in txt.splitlines():
        try:
            name, ts = line.rsplit(" ", 1)
            ts = int(ts)
        except Exception:
            name, ts = line.strip(), -1
        if ts > best_ts:
            best_name, best_ts = name.strip(), ts
    if best_name:
        return best_name
    sessions = list_sessions()
    return sessions[0] if sessions else None

def attach(session: str):
    """Open a Konsole attached to the given tmux session."""
    run(f'konsole -e tmux attach -t {shlex.quote(session)} &')

def kill_session(session: str):
    """Kill a tmux session."""
    run(f'tmux kill-session -t {shlex.quote(session)}')

def restart_session(session: str):
    """Respawn the active window to rerun the last command."""
    run(f'tmux respawn-window -k -t {shlex.quote(session)}')

def last_line(session: str) -> str:
    """Return the last line printed in the active pane of the session."""
    ln = out(f'tmux capture-pane -p -t {shlex.quote(session)} -S -1 2>/dev/null')
    return ln if ln else "(no output)"

# ---------- Tray App ----------
class TmuxTray:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # icons
        self.icon_ok    = QIcon.fromTheme("emblem-success")
        self.icon_error = QIcon.fromTheme("emblem-error")
        self.icon_term  = QIcon.fromTheme("utilities-terminal")

        self.tray = QSystemTrayIcon(self.icon_error)
        self.tray.setToolTip("tmux: no active sessions")

        self.menu = QMenu()
        self.tray.setContextMenu(self.menu)

        # which session the hover tooltip follows
        self.selected_session: Optional[str] = None

        # double-click → attach to selected session or most recent
        self.tray.activated.connect(self.on_activated)

        # periodic refresh
        self.timer = QTimer()
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.refresh_all)

        self.refresh_all()
        self.tray.show()
        self.timer.start()

    # ---------- events ----------
    def on_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason == QSystemTrayIcon.DoubleClick:
            sess = self.get_session_for_focus()
            if sess:
                attach(sess)
            else:
                run('konsole -e tmux &')

    # ---------- helpers ----------
    def get_session_for_focus(self) -> Optional[str]:
        sessions = list_sessions()
        if not sessions:
            self.selected_session = None
            return None
        if self.selected_session in sessions:
            return self.selected_session
        # fallback to the most recent one
        mr = most_recent_session()
        self.selected_session = mr
        return mr

    # ---------- UI ----------
    def rebuild_menu(self):
        self.menu.clear()
        sessions = list_sessions()

        # submenu: hover-session selector (radio style)
        sel_menu = self.menu.addMenu("Hover session")
        group = QActionGroup(self.menu)
        group.setExclusive(True)

        if sessions:
            if self.selected_session not in sessions:
                self.selected_session = most_recent_session() or sessions[0]

            for s in sessions:
                act = QAction(s, self.menu)
                act.setCheckable(True)
                act.setChecked(s == self.selected_session)
                act.triggered.connect(lambda _=False, n=s: self.set_selected(n))
                group.addAction(act)
                sel_menu.addAction(act)
        else:
            na = QAction("(none)", self.menu)
            na.setEnabled(False)
            sel_menu.addAction(na)

        # per-session submenus: open / restart / kill
        if sessions:
            self.menu.addSeparator()
            for s in sessions:
                sub = self.menu.addMenu(s)

                a_open = QAction("open", self.menu)
                a_open.triggered.connect(lambda _=False, n=s: attach(n))
                sub.addAction(a_open)

                a_restart = QAction("restart", self.menu)
                a_restart.triggered.connect(lambda _=False, n=s: restart_session(n))
                sub.addAction(a_restart)

                a_kill = QAction("kill", self.menu)
                a_kill.triggered.connect(lambda _=False, n=s: self.kill_and_refresh(n))
                sub.addAction(a_kill)

        self.menu.addSeparator()
        quit_action = QAction("Quit", self.menu)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)

    def set_selected(self, name: str):
        """Update which session is tracked by the tooltip."""
        self.selected_session = name
        self.refresh_tooltip_and_icon()

    def kill_and_refresh(self, name: str):
        kill_session(name)
        if self.selected_session == name:
            self.selected_session = None
        self.refresh_all()

    def refresh_tooltip_and_icon(self):
        sess = self.get_session_for_focus()
        if sess:
            self.tray.setIcon(self.icon_ok)
            self.tray.setToolTip(f"tmux · {sess}\n{last_line(sess)}")
        else:
            self.tray.setIcon(self.icon_error)
            self.tray.setToolTip("tmux: no active sessions")

    def refresh_all(self):
        self.rebuild_menu()
        self.refresh_tooltip_and_icon()

    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    TmuxTray().run()

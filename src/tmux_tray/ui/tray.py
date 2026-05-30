import logging
import sys
import time
from typing import Dict, List, Optional

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from tmux_tray.tmux.capture import LOG_LINES, LOG_REFRESH_MS, get_pane_tail
from tmux_tray.tmux.process import collect_all_sessions_state
from tmux_tray.tmux.restart import restart_session
from tmux_tray.tmux.sessions import (
    attach,
    kill_session,
    list_sessions,
    most_recent_session,
    open_blank_terminal,
)

log = logging.getLogger("tmux-tray")

SHOW_LOGS_IN_TOOLTIP = True


class TmuxTray:
    def __init__(self) -> None:
        log.debug("TmuxTray.__init__: creating QApplication")
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self._reconcile_xdg_quietly()

        log.debug("TmuxTray.__init__: loading theme icons")
        self.icon_ok = QIcon.fromTheme("emblem-success")
        self.icon_err = QIcon.fromTheme("emblem-error")
        self.icon_term = QIcon.fromTheme("utilities-terminal")

        log.debug("TmuxTray.__init__: creating tray icon and menu")
        self.tray = QSystemTrayIcon(self.icon_err)
        self.tray.setToolTip("tmux: no active sessions")

        self.menu = QMenu()
        self.menu.aboutToShow.connect(lambda: log.debug("menu aboutToShow"))
        self.tray.setContextMenu(self.menu)

        self.selected_session: Optional[str] = None

        self._last_sessions_list: List[str] = []

        self.sel_group: Optional[QActionGroup] = None
        self.sel_actions: Dict[str, QAction] = {}

        self._last_log_text: str = ""
        self._last_log_at: float = 0.0

        self.tray.activated.connect(self.on_activated)

        self.timer = QTimer()
        self.timer.setInterval(10000)
        self.timer.timeout.connect(self.refresh_all)

        log.debug("TmuxTray.__init__: first refresh_all")
        self.refresh_all()
        log.debug("TmuxTray.__init__: tray.show")
        self.tray.show()
        self.timer.start()
        log.debug("TmuxTray.__init__: ready (timer started)")

    def on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            sess = self.get_session_for_focus()
            if sess:
                attach(sess)
            else:
                open_blank_terminal()

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

    def rebuild_menu(self) -> None:
        t0 = time.perf_counter()
        log.debug("rebuild_menu: start")
        self.menu.clear()
        sessions = list_sessions()
        log.debug("rebuild_menu: list_sessions returned %d sessions in %.3fs",
                  len(sessions), time.perf_counter() - t0)

        self._startup_action = QAction("Startup Tmux...", self.menu)
        self._startup_action.triggered.connect(lambda _=False: self.open_startup_dialog())
        self.menu.addAction(self._startup_action)
        self.menu.addSeparator()

        self.sel_group = QActionGroup(self.menu)
        self.sel_group.setExclusive(True)
        self.sel_actions.clear()

        sel_menu = self.menu.addMenu("Hover session")

        if sessions:
            if self.selected_session not in sessions:
                self.selected_session = most_recent_session() or sessions[0]
            for s in sessions:
                act = QAction(s, self.menu)
                act.setCheckable(True)
                act.setChecked(s == self.selected_session)
                act.triggered.connect(lambda _=False, n=s: self.set_selected(n))
                act.hovered.connect(lambda n=s: self.set_selected(n))
                self.sel_group.addAction(act)
                sel_menu.addAction(act)
                self.sel_actions[s] = act
        else:
            na = QAction("(none)", self.menu)
            na.setEnabled(False)
            sel_menu.addAction(na)

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

        log.debug("rebuild_menu: done, %d top-level actions, %d sessions",
                  len(self.menu.actions()), len(sessions))

    def set_selected(self, name: str) -> None:
        self.selected_session = name
        act = self.sel_actions.get(name)
        if act and not act.isChecked():
            act.setChecked(True)
        self.refresh_tooltip_and_icon(force_logs=True)

    def kill_and_refresh(self, name: str) -> None:
        kill_session(name)
        if self.selected_session == name:
            self.selected_session = None
        self.refresh_all()

    def _tooltip_text(self, sess: Optional[str], sessions_count: int) -> str:
        if not sess:
            return "tmux: no active sessions"
        if SHOW_LOGS_IN_TOOLTIP:
            now = time.time()
            if (now - self._last_log_at) * 1000 >= LOG_REFRESH_MS:
                self._last_log_text = get_pane_tail(sess, LOG_LINES)
                self._last_log_at = now
            logs = self._last_log_text or "(no output)"
            return f"tmux · {sess}  |  sessions: {sessions_count}\n{logs}"
        return f"tmux · {sess}  |  sessions: {sessions_count}"

    def refresh_tooltip_and_icon(self, force_logs: bool = False) -> None:
        sessions = list_sessions()
        if sessions:
            collect_all_sessions_state()
            sess = self.get_session_for_focus()
            self.tray.setIcon(self.icon_ok if sess else self.icon_err)
            if force_logs:
                self._last_log_at = 0.0
            self.tray.setToolTip(self._tooltip_text(sess, len(sessions)))
        else:
            self.tray.setIcon(self.icon_err)
            self.tray.setToolTip("tmux: no active sessions")

    def refresh_all(self) -> None:
        t0 = time.perf_counter()
        log.debug("refresh_all: start")
        sessions = list_sessions()
        log.debug("refresh_all: list_sessions %.3fs", time.perf_counter() - t0)
        if sessions != self._last_sessions_list:
            self._last_sessions_list = sessions[:]
            self.rebuild_menu()
            self._last_log_at = 0.0
        self.refresh_tooltip_and_icon()
        log.debug("refresh_all: done in %.3fs", time.perf_counter() - t0)

    def open_startup_dialog(self) -> None:
        from tmux_tray.ui.startup_dialog import open_startup_dialog
        open_startup_dialog()
        self.refresh_all()

    def _reconcile_xdg_quietly(self) -> None:
        t0 = time.perf_counter()
        log.debug("reconcile: start")
        try:
            from tmux_tray.startup.sync import reconcile
            entries, report = reconcile()
            log.debug(
                "reconcile: done in %.3fs (entries=%d, flipped=%s, regenerated=%s, orphans=%s)",
                time.perf_counter() - t0,
                len(entries),
                report.flipped_in_toml,
                report.regenerated_desktops,
                report.removed_orphans,
            )
        except Exception as e:
            log.warning("reconcile failed (%.3fs): %s", time.perf_counter() - t0, e, exc_info=True)

    def run(self) -> None:
        sys.exit(self.app.exec())

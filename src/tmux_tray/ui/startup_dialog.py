"""Startup Tmux dialog — main UI for the feature.

Reconciles TOML ↔ XDG autostart on open and on refresh. Each row exposes
Start/Stop/Edit/Remove actions. "Start now" is conservative: if the entry
is already running, it just shows a warning with PID/details — no kill.
"""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tmux_tray.startup.registry import (
    Entry,
    add_entry,
    remove_entry,
    update_entry,
)
from tmux_tray.startup.runner import detect_running, execute_entry
from tmux_tray.startup.sync import ensure_desktop_for_entry, reconcile
from tmux_tray.startup.xdg import remove_desktop_file
from tmux_tray.tmux.sessions import kill_session
from tmux_tray.ui.add_wizard import AddWizardDialog


class StartupDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Startup Tmux")
        self.resize(900, 480)

        root = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.btn_add = QPushButton("+ Add Script")
        self.btn_refresh = QPushButton("Refresh")
        self.btn_add.clicked.connect(self._on_add)
        self.btn_refresh.clicked.connect(self.refresh)
        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_refresh)
        toolbar.addStretch()
        root.addLayout(toolbar)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Script", "Mode", "Session", "Enabled", "Running", "Actions"]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        root.addWidget(self.table)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        close_btn = buttons.button(QDialogButtonBox.Close)
        if close_btn is not None:
            close_btn.clicked.connect(self.accept)
        root.addWidget(buttons)

        self.refresh()

    def refresh(self) -> None:
        try:
            entries, _ = reconcile()
        except Exception as e:
            QMessageBox.critical(self, "Sync error", f"Failed to reconcile config:\n{e}")
            entries = []

        self.table.setRowCount(0)
        for entry in entries:
            self._add_row(entry)

    def _add_row(self, entry: Entry) -> None:
        try:
            running = detect_running(entry)
        except Exception:
            running = None

        row = self.table.rowCount()
        self.table.insertRow(row)

        items = [
            QTableWidgetItem(entry.name),
            QTableWidgetItem(entry.path),
            QTableWidgetItem(entry.mode),
            QTableWidgetItem(entry.session_name),
            QTableWidgetItem("✓" if entry.enabled else "✗"),
            QTableWidgetItem("● running" if running else "—"),
        ]
        for col, item in enumerate(items):
            if col in (4, 5):
                item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, col, item)

        actions = QWidget()
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(2, 2, 2, 2)
        actions_layout.setSpacing(2)

        btn_start = QPushButton("▶")
        btn_start.setToolTip("Start now")
        btn_start.clicked.connect(lambda _checked=False, e=entry: self._on_start(e))
        btn_stop = QPushButton("⏹")
        btn_stop.setToolTip("Stop tmux session")
        btn_stop.clicked.connect(lambda _checked=False, e=entry: self._on_stop(e))
        btn_edit = QPushButton("✎")
        btn_edit.setToolTip("Edit")
        btn_edit.clicked.connect(lambda _checked=False, e=entry: self._on_edit(e))
        btn_remove = QPushButton("🗑")
        btn_remove.setToolTip("Remove")
        btn_remove.clicked.connect(lambda _checked=False, e=entry: self._on_remove(e))

        for b in (btn_start, btn_stop, btn_edit, btn_remove):
            b.setFixedWidth(36)
            actions_layout.addWidget(b)
        actions_layout.addStretch()

        self.table.setCellWidget(row, 6, actions)

    def _on_add(self) -> None:
        dlg = AddWizardDialog(self)
        if dlg.exec() != QDialog.Accepted or dlg.entry is None:
            return
        try:
            add_entry(dlg.entry)
            ensure_desktop_for_entry(dlg.entry)
        except Exception as e:
            QMessageBox.critical(self, "Add failed", f"Could not add entry:\n{e}")
            return
        self.refresh()

    def _on_edit(self, entry: Entry) -> None:
        dlg = AddWizardDialog(self, existing=entry)
        if dlg.exec() != QDialog.Accepted or dlg.entry is None:
            return
        updated = dlg.entry
        try:
            update_entry(
                entry.slug,
                name=updated.name,
                path=updated.path,
                cwd=updated.cwd,
                command=updated.command,
                mode=updated.mode,
                session_name=updated.session_name,
                enabled=updated.enabled,
            )
            ensure_desktop_for_entry(updated)
        except Exception as e:
            QMessageBox.critical(self, "Edit failed", f"Could not update entry:\n{e}")
            return
        self.refresh()

    def _on_remove(self, entry: Entry) -> None:
        reply = QMessageBox.question(
            self,
            f"Remove '{entry.name}'?",
            (
                "Remove this entry from Startup Tmux?\n\n"
                "The autostart .desktop file will be deleted.\n"
                "The script file itself will not be touched."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            remove_entry(entry.slug)
            remove_desktop_file(entry.slug)
        except Exception as e:
            QMessageBox.critical(self, "Remove failed", f"Could not remove entry:\n{e}")
            return
        self.refresh()

    def _on_start(self, entry: Entry) -> None:
        try:
            running = detect_running(entry)
        except Exception:
            running = None

        if running is not None:
            pid_block = ""
            if running.pids:
                pids = ", ".join(f"PID {p.pid}" for p in running.pids[:5])
                pid_block = f"\n\nPIDs: {pids}"
            QMessageBox.warning(
                self,
                "Already running",
                (
                    f"Entry '{entry.name}' is already running.\n\n"
                    f"Method: {running.method}\n"
                    f"Details: {running.details}{pid_block}\n\n"
                    f"No action taken."
                ),
            )
            return

        try:
            rc = execute_entry(entry)
        except Exception as e:
            QMessageBox.critical(self, "Start failed", f"Exception while starting:\n{e}")
            return

        if rc != 0:
            QMessageBox.critical(
                self,
                "Start failed",
                f"'{entry.name}' did not start (exit code {rc}). Check the terminal output.",
            )
        self.refresh()

    def _on_stop(self, entry: Entry) -> None:
        try:
            kill_session(entry.session_name)
        except Exception as e:
            QMessageBox.critical(self, "Stop failed", f"Could not stop session:\n{e}")
            return
        self.refresh()


def open_startup_dialog(parent: Optional[QWidget] = None) -> None:
    dlg = StartupDialog(parent)
    dlg.exec()

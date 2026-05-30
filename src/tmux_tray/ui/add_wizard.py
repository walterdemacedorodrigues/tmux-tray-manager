"""Add/Edit dialog for a Startup Tmux entry.

Runs the 3 detections on the chosen script:
  - is_self_tmux  → suggests mode 'self-managed' if positive
  - scan_xdg_autostart  → warns if the script is already in another autostart .desktop
  - find_running_pids  → informs which PIDs currently match
"""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from tmux_tray.startup.detection import (
    find_running_pids,
    is_self_tmux,
    scan_xdg_autostart,
)
from tmux_tray.startup.naming import (
    derive_name_and_id,
    is_valid_slug,
    slugify,
    suggest_command,
)
from tmux_tray.startup.registry import Entry, load_entries
from tmux_tray.startup.xdg import desktop_file_path


class AddWizardDialog(QDialog):
    def __init__(self, parent=None, existing: Optional[Entry] = None) -> None:
        super().__init__(parent)
        self.existing = existing
        self.entry: Optional[Entry] = None
        self.setWindowTitle("Edit Startup Entry" if existing else "Add Startup Entry")
        self.resize(680, 560)

        self._slug_is_auto = existing is None
        self._session_is_auto = existing is None
        self._command_is_auto = existing is None
        self._last_path_seen = ""

        layout = QVBoxLayout(self)

        path_group = QGroupBox("Script *")
        path_layout = QHBoxLayout(path_group)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("/path/to/script.sh")
        btn_pick = QPushButton("Browse…")
        btn_pick.clicked.connect(self._on_pick_file)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(btn_pick)
        layout.addWidget(path_group)

        self.detection_label = QLabel("Pick a script to see detection results.")
        self.detection_label.setWordWrap(True)
        self.detection_label.setTextFormat(Qt.TextFormat.RichText)
        self.detection_label.setStyleSheet(
            "QLabel { padding: 10px; background: rgba(128,128,128,0.08); "
            "border-radius: 4px; }"
        )
        layout.addWidget(self.detection_label)

        form_group = QGroupBox("Entry")
        form = QFormLayout(form_group)
        self.name_edit = QLineEdit()
        self.slug_edit = QLineEdit()
        self.slug_edit.setToolTip(
            "Internal identifier — lowercase, digits, '-' or '_'.\n"
            "Used in the tmux session name, in the autostart .desktop\n"
            "filename, and as a stable key in tmux-tray's config.\n"
            "Auto-generated from Name; edit only if you need a custom one."
        )
        self.cwd_edit = QLineEdit()
        self.cwd_edit.setPlaceholderText("optional — defaults to script's directory")
        self.command_edit = QLineEdit()
        self.command_edit.setPlaceholderText("optional — runs the script directly if empty")
        self.command_edit.setToolTip(
            "Override the command used to launch the script.\n"
            "Leave empty to execute the script directly (needs shebang + chmod +x).\n"
            "Use this for interpreters: e.g. 'python3 /path/start.py', 'node app.js'.\n"
            "Auto-filled when the script's extension implies an interpreter."
        )
        self.session_edit = QLineEdit()
        self.session_edit.setToolTip("The tmux session name. Defaults to ID.")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["tmux-wrapped", "self-managed"])
        self.enabled_check = QCheckBox("Enable autostart at login")
        self.enabled_check.setChecked(True)

        form.addRow("Name *:", self.name_edit)
        form.addRow("ID *:", self.slug_edit)
        form.addRow("Working directory:", self.cwd_edit)
        form.addRow("Command:", self.command_edit)
        form.addRow("Tmux session name *:", self.session_edit)
        form.addRow("Mode *:", self.mode_combo)
        form.addRow("", self.enabled_check)
        layout.addWidget(form_group)

        required_note = QLabel("<small><i>Fields marked with * are required.</i></small>")
        required_note.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(required_note)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.path_edit.editingFinished.connect(self._on_path_finished)
        self.name_edit.textEdited.connect(self._on_name_edited)
        self.slug_edit.textEdited.connect(self._on_slug_edited)
        self.session_edit.textEdited.connect(self._on_session_edited)
        self.command_edit.textEdited.connect(self._on_command_edited)

        if existing is not None:
            self._fill_from_entry(existing)

    def _fill_from_entry(self, e: Entry) -> None:
        self.path_edit.setText(e.path)
        self._last_path_seen = e.path
        self.name_edit.setText(e.name)
        self.slug_edit.setText(e.slug)
        self.slug_edit.setEnabled(False)
        if e.cwd:
            self.cwd_edit.setText(e.cwd)
        if e.command:
            self.command_edit.setText(e.command)
        self.session_edit.setText(e.session_name)
        idx = self.mode_combo.findText(e.mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        self.enabled_check.setChecked(e.enabled)
        self._run_detections(Path(e.path))

    def _on_pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select script",
            str(Path.home()),
            "All Files (*)",
        )
        if not path:
            return
        self.path_edit.setText(path)
        self._last_path_seen = path
        self._apply_path_change(path)

    def _on_path_finished(self) -> None:
        text = self.path_edit.text().strip()
        if text == self._last_path_seen:
            return
        self._last_path_seen = text
        if text:
            self._apply_path_change(text)

    def _apply_path_change(self, path_str: str) -> None:
        p = Path(path_str)
        if self.existing is None:
            self._auto_fill_from_path(p)
        if p.exists():
            self._run_detections(p)
        else:
            self.detection_label.setText(
                f"<span style='color:#c0392b'>Path does not exist: {path_str}</span>"
            )

    def _auto_fill_from_path(self, p: Path) -> None:
        pretty_name, slug = derive_name_and_id(p)
        if not self.name_edit.text():
            self.name_edit.setText(pretty_name)
        if self._slug_is_auto and not self.slug_edit.text():
            self.slug_edit.setText(slug)
        if self._session_is_auto and not self.session_edit.text():
            self.session_edit.setText(slug)
        if not self.cwd_edit.text():
            self.cwd_edit.setText(str(p.parent))
        if self._command_is_auto and not self.command_edit.text():
            suggested = suggest_command(p)
            if suggested:
                self.command_edit.setText(suggested)

    def _on_name_edited(self, new_name: str) -> None:
        if self._slug_is_auto:
            derived = slugify(new_name) if new_name else ""
            self.slug_edit.setText(derived)
            if self._session_is_auto:
                self.session_edit.setText(derived)

    def _on_slug_edited(self, _text: str) -> None:
        self._slug_is_auto = False
        if self._session_is_auto:
            self.session_edit.setText(self.slug_edit.text())

    def _on_session_edited(self, _text: str) -> None:
        self._session_is_auto = False

    def _on_command_edited(self, _text: str) -> None:
        self._command_is_auto = False

    def _run_detections(self, path: Path) -> None:
        if not path.exists():
            self.detection_label.setText(f"<span style='color:#c0392b'>Path does not exist: {path}</span>")
            return

        msgs: list[str] = []

        try:
            self_tmux = is_self_tmux(path)
        except Exception:
            self_tmux = False

        if self_tmux:
            msgs.append(
                "🔍 <b>Self-tmux detected</b>: this script invokes tmux on its own. "
                "Recommended mode: <b>self-managed</b> — tmux-tray will just execute it "
                "without wrapping in another tmux session."
            )
            if self.existing is None:
                idx = self.mode_combo.findText("self-managed")
                if idx >= 0:
                    self.mode_combo.setCurrentIndex(idx)
        else:
            msgs.append(
                "✓ <b>No tmux invocations found</b>: will run as <b>tmux-wrapped</b> "
                "— tmux-tray creates the tmux session."
            )

        existing_desktops = scan_xdg_autostart(str(path))
        if self.existing is not None:
            our_own = desktop_file_path(self.existing.slug)
            existing_desktops = [d for d in existing_desktops if d != our_own]
        if existing_desktops:
            names = ", ".join(f"<code>{d.name}</code>" for d in existing_desktops)
            msgs.append(
                "⚠️ <b>Already in XDG autostart</b>: this script is referenced by "
                f"{names}. Adding it here will create a duplicate autostart entry. "
                "Consider removing the other .desktop file manually first."
            )

        try:
            running = find_running_pids(str(path))
        except Exception:
            running = []
        if running:
            pid_strs = ", ".join(f"PID {p.pid}" for p in running[:5])
            extra = f" (+{len(running) - 5} more)" if len(running) > 5 else ""
            msgs.append(f"ℹ️ <b>Currently running</b>: {pid_strs}{extra}.")

        self.detection_label.setText("<br/><br/>".join(msgs))

    def _on_accept(self) -> None:
        path = self.path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "Missing script", "Please select a script.")
            return
        if not Path(path).is_file():
            QMessageBox.warning(self, "Invalid path", f"Script does not exist:\n{path}")
            return

        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Please enter a name.")
            return

        slug = self.slug_edit.text().strip()
        if not is_valid_slug(slug):
            QMessageBox.warning(
                self,
                "Invalid ID",
                "ID must use only lowercase letters, digits, '-' and '_', "
                "starting with a letter or digit.",
            )
            return

        if self.existing is None:
            existing_slugs = {e.slug for e in load_entries()}
            if slug in existing_slugs:
                QMessageBox.warning(
                    self,
                    "ID already exists",
                    f"An entry with ID '{slug}' already exists.",
                )
                return

        session_name = self.session_edit.text().strip() or slug
        cwd_text = self.cwd_edit.text().strip()
        cwd = cwd_text if cwd_text else None
        command_text = self.command_edit.text().strip()
        command = command_text if command_text else None
        mode = self.mode_combo.currentText()
        enabled = self.enabled_check.isChecked()

        self.entry = Entry(
            slug=slug,
            name=name,
            path=path,
            session_name=session_name,
            mode=mode,  # type: ignore[arg-type]
            cwd=cwd,
            enabled=enabled,
            command=command,
        )
        self.accept()

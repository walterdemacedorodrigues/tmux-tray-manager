"""Add/Edit dialog for a Startup Tmux entry.

Runs the 3 detections on the chosen script:
  - is_self_tmux  → suggests mode 'self-managed' if positive
  - scan_xdg_autostart  → warns if the script is already in another autostart .desktop
  - find_running_pids  → informs which PIDs currently match
"""

import re
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
from tmux_tray.startup.registry import Entry, load_entries
from tmux_tray.startup.xdg import desktop_file_path

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def slugify(text: str) -> str:
    s = text.lower()
    s = re.sub(r"[^a-z0-9_-]+", "-", s).strip("-")
    if not s:
        return "entry"
    if not s[0].isalnum():
        s = "e-" + s
    return s


class AddWizardDialog(QDialog):
    def __init__(self, parent=None, existing: Optional[Entry] = None) -> None:
        super().__init__(parent)
        self.existing = existing
        self.entry: Optional[Entry] = None
        self.setWindowTitle("Edit Startup Entry" if existing else "Add Startup Entry")
        self.resize(640, 520)

        layout = QVBoxLayout(self)

        path_group = QGroupBox("Script")
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
        self.cwd_edit = QLineEdit()
        self.cwd_edit.setPlaceholderText("optional — defaults to script directory")
        self.session_edit = QLineEdit()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["tmux-wrapped", "self-managed"])
        self.enabled_check = QCheckBox("Enable autostart at login")
        self.enabled_check.setChecked(True)

        form.addRow("Name:", self.name_edit)
        form.addRow("Slug:", self.slug_edit)
        form.addRow("Working directory:", self.cwd_edit)
        form.addRow("Tmux session name:", self.session_edit)
        form.addRow("Mode:", self.mode_combo)
        form.addRow("", self.enabled_check)
        layout.addWidget(form_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if existing is not None:
            self._fill_from_entry(existing)

    def _fill_from_entry(self, e: Entry) -> None:
        self.path_edit.setText(e.path)
        self.name_edit.setText(e.name)
        self.slug_edit.setText(e.slug)
        self.slug_edit.setEnabled(False)
        if e.cwd:
            self.cwd_edit.setText(e.cwd)
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
        p = Path(path)
        if self.existing is None:
            stem = p.stem
            self.name_edit.setText(stem.replace("_", " ").replace("-", " ").title())
            self.slug_edit.setText(slugify(stem))
            self.cwd_edit.setText(str(p.parent))
            self.session_edit.setText(slugify(stem))
        self._run_detections(p)

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
        if not _SLUG_RE.match(slug):
            QMessageBox.warning(
                self,
                "Invalid slug",
                "Slug must use only lowercase letters, digits, '-' and '_', "
                "starting with a letter or digit.",
            )
            return

        if self.existing is None:
            existing_slugs = {e.slug for e in load_entries()}
            if slug in existing_slugs:
                QMessageBox.warning(
                    self,
                    "Slug exists",
                    f"An entry with slug '{slug}' already exists.",
                )
                return

        session_name = self.session_edit.text().strip() or slug
        cwd_text = self.cwd_edit.text().strip()
        cwd = cwd_text if cwd_text else None
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
        )
        self.accept()

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from PySide6.QtWidgets import QSystemTrayIcon


def notify(tray: "Optional[QSystemTrayIcon]", title: str, text: str, msecs: int = 2600) -> None:
    if not tray:
        return
    try:
        from PySide6.QtWidgets import QSystemTrayIcon
        tray.showMessage(title, text, QSystemTrayIcon.Information, msecs)
    except Exception:
        pass

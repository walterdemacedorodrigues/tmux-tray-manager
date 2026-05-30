import argparse
import logging
import os
import signal
import sys

from tmux_tray import __version__

log = logging.getLogger("tmux-tray")


def _install_qt_message_handler() -> None:
    """Forward every Qt warning/error to stderr so they're visible to the user.

    Qt swallows most diagnostics by default. We always want to see them when
    something goes wrong with icons, the tray, or the event loop.
    """
    try:
        from PySide6.QtCore import QtMsgType, qInstallMessageHandler
    except Exception:
        return

    levels = {
        QtMsgType.QtDebugMsg: "DEBUG",
        QtMsgType.QtInfoMsg: "INFO",
        QtMsgType.QtWarningMsg: "WARNING",
        QtMsgType.QtCriticalMsg: "CRITICAL",
        QtMsgType.QtFatalMsg: "FATAL",
    }

    def handler(msg_type, context, msg):
        lvl = levels.get(msg_type, "?")
        loc = ""
        if context is not None and getattr(context, "file", None):
            loc = f" ({context.file}:{context.line})"
        print(f"[QT {lvl}] {msg}{loc}", file=sys.stderr, flush=True)

    qInstallMessageHandler(handler)


def _install_sigint_handler() -> None:
    """Let Ctrl+C kill the app even while the Qt event loop is running.

    Without this, Python signals are blocked while the C event loop is spinning
    and Ctrl+C only fires when control briefly returns to Python.
    """
    signal.signal(signal.SIGINT, signal.SIG_DFL)


def _setup_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s.%(msecs)03d [%(name)s %(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="tmux-tray",
        description="System tray monitor for tmux sessions (KDE/Wayland).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--start",
        metavar="SLUG",
        help="Run a startup entry by slug (used by the XDG autostart .desktop).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Verbose diagnostics to stderr (timing, menu rebuild, reconcile).",
    )
    args = parser.parse_args()

    debug = args.debug or bool(os.environ.get("TMUX_TRAY_DEBUG"))
    _setup_logging(debug)
    _install_qt_message_handler()
    _install_sigint_handler()

    if args.start:
        from tmux_tray.startup.runner import start_by_slug
        sys.exit(start_by_slug(args.start))

    log.debug("starting TmuxTray")
    from tmux_tray.ui.tray import TmuxTray
    TmuxTray().run()


if __name__ == "__main__":
    main()

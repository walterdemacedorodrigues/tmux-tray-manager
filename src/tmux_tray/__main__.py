import argparse
import sys

from tmux_tray import __version__


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
    args = parser.parse_args()

    if args.start:
        from tmux_tray.startup.runner import start_by_slug
        sys.exit(start_by_slug(args.start))

    from tmux_tray.ui.tray import TmuxTray
    TmuxTray().run()


if __name__ == "__main__":
    main()

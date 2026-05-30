import os
from pathlib import Path

APP_NAME = "tmux-tray"


def _xdg_config_home() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base)
    return Path.home() / ".config"


def config_dir() -> Path:
    return _xdg_config_home() / APP_NAME


def ensure_config_dir() -> Path:
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def startup_toml_path() -> Path:
    return config_dir() / "startup.toml"


def autostart_dir() -> Path:
    return _xdg_config_home() / "autostart"


def ensure_autostart_dir() -> Path:
    d = autostart_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d

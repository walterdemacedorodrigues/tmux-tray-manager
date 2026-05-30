from pathlib import Path

from tmux_tray.config import (
    autostart_dir,
    config_dir,
    ensure_autostart_dir,
    ensure_config_dir,
    startup_toml_path,
)


def test_config_dir_respects_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config_dir() == tmp_path / "tmux-tray"


def test_config_dir_falls_back_to_home(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert config_dir() == tmp_path / ".config" / "tmux-tray"


def test_ensure_config_dir_creates(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    d = ensure_config_dir()
    assert d.is_dir()


def test_startup_toml_path(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert startup_toml_path() == tmp_path / "tmux-tray" / "startup.toml"


def test_autostart_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert autostart_dir() == tmp_path / "autostart"


def test_ensure_autostart_dir_creates(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    d = ensure_autostart_dir()
    assert d.is_dir()

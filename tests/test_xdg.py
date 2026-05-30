from tmux_tray.startup.registry import Entry
from tmux_tray.startup.xdg import (
    DESKTOP_PREFIX,
    desktop_file_path,
    is_hidden,
    list_managed_slugs,
    remove_desktop_file,
    render_desktop,
    write_desktop_file,
)


def make_entry(slug="james", enabled=True, **overrides) -> Entry:
    defaults: dict = dict(
        slug=slug,
        name=slug.title(),
        path=f"/home/user/{slug}/run.sh",
        session_name=slug,
        mode="self-managed",
        cwd=f"/home/user/{slug}",
        enabled=enabled,
    )
    defaults.update(overrides)
    return Entry(**defaults)


def test_desktop_file_path_uses_prefix(tmp_path):
    p = desktop_file_path("james", autostart_root=tmp_path)
    assert p == tmp_path / f"{DESKTOP_PREFIX}james.desktop"


def test_render_contains_required_fields():
    out = render_desktop(make_entry("james"))
    assert "[Desktop Entry]" in out
    assert "Type=Application" in out
    assert "Name=James" in out
    assert "Exec=tmux-tray --start james" in out
    assert "Icon=tmux-tray" in out
    assert "X-TmuxTray-Slug=james" in out


def test_render_disabled_sets_hidden_true():
    out = render_desktop(make_entry("james", enabled=False))
    assert "Hidden=true" in out


def test_render_enabled_sets_hidden_false():
    out = render_desktop(make_entry("james", enabled=True))
    assert "Hidden=false" in out


def test_render_escapes_newlines_in_name():
    out = render_desktop(make_entry("james", name="Line1\nLine2"))
    assert "Name=Line1\\nLine2" in out
    assert "Line2" not in out.replace("\\nLine2", "")


def test_write_and_read_back(tmp_path):
    e = make_entry("james")
    p = write_desktop_file(e, autostart_root=tmp_path)
    assert p.exists()
    body = p.read_text()
    assert "Exec=tmux-tray --start james" in body


def test_write_creates_autostart_dir(tmp_path):
    nested = tmp_path / "deeper" / "autostart"
    e = make_entry("james")
    p = write_desktop_file(e, autostart_root=nested)
    assert p.exists()
    assert p.parent == nested


def test_remove_existing_returns_true(tmp_path):
    write_desktop_file(make_entry("a"), autostart_root=tmp_path)
    assert remove_desktop_file("a", autostart_root=tmp_path) is True
    assert not desktop_file_path("a", autostart_root=tmp_path).exists()


def test_remove_missing_returns_false(tmp_path):
    assert remove_desktop_file("ghost", autostart_root=tmp_path) is False


def test_is_hidden_reads_enabled_entry(tmp_path):
    write_desktop_file(make_entry("a", enabled=True), autostart_root=tmp_path)
    assert is_hidden("a", autostart_root=tmp_path) is False


def test_is_hidden_reads_disabled_entry(tmp_path):
    write_desktop_file(make_entry("a", enabled=False), autostart_root=tmp_path)
    assert is_hidden("a", autostart_root=tmp_path) is True


def test_is_hidden_returns_none_for_missing(tmp_path):
    assert is_hidden("ghost", autostart_root=tmp_path) is None


def test_list_managed_slugs(tmp_path):
    write_desktop_file(make_entry("alpha"), autostart_root=tmp_path)
    write_desktop_file(make_entry("beta"), autostart_root=tmp_path)
    (tmp_path / "other.desktop").write_text("[Desktop Entry]\nName=Other\n")
    slugs = list_managed_slugs(autostart_root=tmp_path)
    assert slugs == ["alpha", "beta"]


def test_list_managed_slugs_empty_for_missing_dir(tmp_path):
    nonexistent = tmp_path / "absent"
    assert list_managed_slugs(autostart_root=nonexistent) == []


def test_write_is_atomic_no_tmp_leftover(tmp_path):
    write_desktop_file(make_entry("a"), autostart_root=tmp_path)
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == []

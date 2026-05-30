import pytest

from tmux_tray.startup.registry import (
    Entry,
    add_entry,
    find_entry,
    load_entries,
    remove_entry,
    save_entries,
    update_entry,
)


@pytest.fixture
def toml_path(tmp_path):
    return tmp_path / "startup.toml"


def make_entry(slug="james", **overrides) -> Entry:
    defaults: dict = dict(
        slug=slug,
        name=slug.title(),
        path=f"/home/user/projects/{slug}/run.sh",
        session_name=slug,
        mode="self-managed",
        cwd=f"/home/user/projects/{slug}",
        enabled=True,
    )
    defaults.update(overrides)
    return Entry(**defaults)


def test_load_missing_file_returns_empty(toml_path):
    assert load_entries(toml_path) == []


def test_save_then_load_roundtrip(toml_path):
    e1 = make_entry("james")
    e2 = make_entry("foo", mode="tmux-wrapped", cwd=None)
    save_entries([e1, e2], toml_path)
    loaded = load_entries(toml_path)
    assert loaded == [e1, e2]


def test_save_empty_list_creates_empty_file(toml_path):
    save_entries([], toml_path)
    assert toml_path.exists()
    assert toml_path.read_text() == ""


def test_save_handles_special_chars_in_paths(toml_path):
    weird_path = '/home/user/with "quotes" and \\backslash/run.sh'
    e = make_entry("weird", path=weird_path)
    save_entries([e], toml_path)
    loaded = load_entries(toml_path)
    assert loaded[0].path == weird_path


def test_entry_without_cwd_omits_field(toml_path):
    e = make_entry("plain", cwd=None)
    save_entries([e], toml_path)
    body = toml_path.read_text()
    assert "cwd =" not in body
    loaded = load_entries(toml_path)
    assert loaded[0].cwd is None


def test_add_entry_appends(toml_path):
    add_entry(make_entry("a"), toml_path)
    add_entry(make_entry("b"), toml_path)
    slugs = [e.slug for e in load_entries(toml_path)]
    assert slugs == ["a", "b"]


def test_add_duplicate_slug_raises(toml_path):
    add_entry(make_entry("dup"), toml_path)
    with pytest.raises(ValueError, match="already exists"):
        add_entry(make_entry("dup"), toml_path)


def test_remove_entry_existing(toml_path):
    save_entries([make_entry("a"), make_entry("b")], toml_path)
    assert remove_entry("a", toml_path) is True
    remaining = [e.slug for e in load_entries(toml_path)]
    assert remaining == ["b"]


def test_remove_entry_missing_returns_false(toml_path):
    save_entries([make_entry("a")], toml_path)
    assert remove_entry("nonexistent", toml_path) is False


def test_find_entry(toml_path):
    save_entries([make_entry("a"), make_entry("b")], toml_path)
    found = find_entry("b", toml_path)
    assert found is not None and found.slug == "b"
    assert find_entry("nonexistent", toml_path) is None


def test_update_entry_modifies_fields(toml_path):
    save_entries([make_entry("a")], toml_path)
    updated = update_entry("a", path=toml_path, enabled=False, name="Renamed")
    assert updated is not None
    assert updated.enabled is False
    assert updated.name == "Renamed"
    persisted = find_entry("a", toml_path)
    assert persisted is not None
    assert persisted.enabled is False
    assert persisted.name == "Renamed"


def test_update_entry_missing_returns_none(toml_path):
    updated = update_entry("ghost", path=toml_path, enabled=False)
    assert updated is None


def test_update_entry_invalid_field_raises(toml_path):
    save_entries([make_entry("a")], toml_path)
    with pytest.raises(AttributeError):
        update_entry("a", path=toml_path, bogus_field="x")


def test_update_entry_invalid_mode_raises(toml_path):
    save_entries([make_entry("a")], toml_path)
    with pytest.raises(ValueError, match="Invalid mode"):
        update_entry("a", path=toml_path, mode="garbage")


def test_load_invalid_mode_skips_entry(toml_path):
    toml_path.write_text(
        '[[entry]]\nslug = "good"\nname = "Good"\npath = "/x"\n'
        'mode = "tmux-wrapped"\nsession_name = "good"\nenabled = true\n\n'
        '[[entry]]\nslug = "bad"\nname = "Bad"\npath = "/y"\n'
        'mode = "garbage"\nsession_name = "bad"\nenabled = true\n'
    )
    entries = load_entries(toml_path)
    assert [e.slug for e in entries] == ["good"]


def test_load_missing_required_field_skips_entry(toml_path):
    toml_path.write_text(
        '[[entry]]\nslug = "good"\nname = "Good"\npath = "/x"\n'
        'mode = "tmux-wrapped"\nsession_name = "good"\n\n'
        '[[entry]]\nslug = "incomplete"\nname = "Inc"\n'
    )
    entries = load_entries(toml_path)
    assert [e.slug for e in entries] == ["good"]


def test_load_malformed_toml_returns_empty(toml_path):
    toml_path.write_text("this is not [[ valid toml @@")
    assert load_entries(toml_path) == []


def test_save_is_atomic_no_tmp_leftover(toml_path):
    save_entries([make_entry("a")], toml_path)
    leftovers = list(toml_path.parent.glob("*.tmp"))
    assert leftovers == []


def test_entry_command_roundtrip(toml_path):
    e = make_entry("py", command="python3 /opt/app/start.py --port 8080")
    save_entries([e], toml_path)
    loaded = load_entries(toml_path)
    assert loaded[0].command == "python3 /opt/app/start.py --port 8080"


def test_entry_without_command_omits_field(toml_path):
    e = make_entry("plain", command=None)
    save_entries([e], toml_path)
    body = toml_path.read_text()
    assert "command =" not in body
    loaded = load_entries(toml_path)
    assert loaded[0].command is None


def test_load_legacy_entry_without_command_field(toml_path):
    """Entries written before the command field existed must still load."""
    toml_path.write_text(
        '[[entry]]\nslug = "legacy"\nname = "Legacy"\npath = "/x/run.sh"\n'
        'mode = "tmux-wrapped"\nsession_name = "legacy"\nenabled = true\n'
    )
    entries = load_entries(toml_path)
    assert len(entries) == 1
    assert entries[0].command is None


def test_update_entry_can_set_and_clear_command(toml_path):
    save_entries([make_entry("a", command=None)], toml_path)
    updated = update_entry("a", path=toml_path, command="python3 main.py")
    assert updated is not None and updated.command == "python3 main.py"
    cleared = update_entry("a", path=toml_path, command=None)
    assert cleared is not None and cleared.command is None
    loaded = load_entries(toml_path)
    assert loaded[0].command is None

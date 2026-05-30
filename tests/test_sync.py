from tmux_tray.startup.registry import Entry
from tmux_tray.startup.sync import ensure_desktop_for_entry, reconcile


def make_entry(slug, enabled=True):
    return Entry(
        slug=slug,
        name=slug.title(),
        path=f"/x/{slug}/run.sh",
        session_name=slug,
        mode="tmux-wrapped",
        enabled=enabled,
    )


def test_reconcile_no_entries_is_noop():
    entries, report = reconcile(
        load_entries_fn=lambda: [],
        save_entries_fn=lambda x: None,
        is_hidden_fn=lambda s: None,
        write_desktop_fn=lambda e: None,
        remove_desktop_fn=lambda s: True,
        list_slugs_fn=lambda: [],
    )
    assert entries == []
    assert report.flipped_in_toml == []
    assert report.regenerated_desktops == []
    assert report.removed_orphans == []


def test_reconcile_regenerates_missing_desktop():
    e = make_entry("a", enabled=True)
    written = []
    entries, report = reconcile(
        load_entries_fn=lambda: [e],
        save_entries_fn=lambda lst: None,
        is_hidden_fn=lambda s: None,
        write_desktop_fn=lambda entry: written.append(entry.slug),
        remove_desktop_fn=lambda s: True,
        list_slugs_fn=lambda: [],
    )
    assert report.regenerated_desktops == ["a"]
    assert written == ["a"]


def test_reconcile_desktop_hidden_flips_toml_to_disabled():
    e = make_entry("a", enabled=True)
    saved: list[list[Entry]] = []
    entries, report = reconcile(
        load_entries_fn=lambda: [e],
        save_entries_fn=lambda lst: saved.append(list(lst)),
        is_hidden_fn=lambda s: True,
        write_desktop_fn=lambda entry: None,
        remove_desktop_fn=lambda s: True,
        list_slugs_fn=lambda: ["a"],
    )
    assert report.flipped_in_toml == ["a"]
    assert entries[0].enabled is False
    assert saved and saved[0][0].enabled is False


def test_reconcile_desktop_not_hidden_flips_toml_to_enabled():
    e = make_entry("a", enabled=False)
    saved: list[list[Entry]] = []
    entries, report = reconcile(
        load_entries_fn=lambda: [e],
        save_entries_fn=lambda lst: saved.append(list(lst)),
        is_hidden_fn=lambda s: False,
        write_desktop_fn=lambda entry: None,
        remove_desktop_fn=lambda s: True,
        list_slugs_fn=lambda: ["a"],
    )
    assert report.flipped_in_toml == ["a"]
    assert entries[0].enabled is True


def test_reconcile_no_save_when_in_sync():
    e = make_entry("a", enabled=True)
    save_calls = []
    entries, report = reconcile(
        load_entries_fn=lambda: [e],
        save_entries_fn=lambda lst: save_calls.append(lst),
        is_hidden_fn=lambda s: False,
        write_desktop_fn=lambda entry: None,
        remove_desktop_fn=lambda s: True,
        list_slugs_fn=lambda: ["a"],
    )
    assert report.flipped_in_toml == []
    assert save_calls == []


def test_reconcile_removes_orphan_desktops():
    e = make_entry("a", enabled=True)
    removed = []
    entries, report = reconcile(
        load_entries_fn=lambda: [e],
        save_entries_fn=lambda lst: None,
        is_hidden_fn=lambda s: False,
        write_desktop_fn=lambda entry: None,
        remove_desktop_fn=lambda s: removed.append(s) or True,
        list_slugs_fn=lambda: ["a", "ghost-1", "ghost-2"],
    )
    assert removed == ["ghost-1", "ghost-2"]
    assert report.removed_orphans == ["ghost-1", "ghost-2"]


def test_reconcile_regenerated_takes_precedence_over_flip():
    """Missing .desktop is regenerated; no flip even if states implied otherwise."""
    e = make_entry("a", enabled=True)
    saved = []
    written = []
    entries, report = reconcile(
        load_entries_fn=lambda: [e],
        save_entries_fn=lambda lst: saved.append(lst),
        is_hidden_fn=lambda s: None,  # missing
        write_desktop_fn=lambda entry: written.append(entry.slug),
        remove_desktop_fn=lambda s: True,
        list_slugs_fn=lambda: [],
    )
    assert report.regenerated_desktops == ["a"]
    assert report.flipped_in_toml == []
    assert saved == []
    assert written == ["a"]


def test_ensure_desktop_for_entry_calls_write():
    written = []
    ensure_desktop_for_entry(make_entry("x"), write_fn=lambda e: written.append(e.slug))
    assert written == ["x"]

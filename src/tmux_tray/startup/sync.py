"""Bidirectional sync between the TOML registry and the XDG autostart .desktop files.

Reconciliation rules (called on tray start and when the Startup dialog refreshes):

  1. .desktop missing for a TOML entry  → regenerate it (entry.enabled wins).
  2. .desktop Hidden field disagrees with entry.enabled  → .desktop wins,
     update TOML (this is how KDE Autostart toggles flow back into us).
  3. .desktop file matching our naming prefix but no matching TOML entry
     → orphan; remove it.

All side effects go through injected functions so the logic is unit-tested
without touching the real filesystem.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

from tmux_tray.startup.registry import Entry, load_entries, save_entries
from tmux_tray.startup.xdg import (
    is_hidden,
    list_managed_slugs,
    remove_desktop_file,
    write_desktop_file,
)


@dataclass
class SyncReport:
    flipped_in_toml: list[str] = field(default_factory=list)
    regenerated_desktops: list[str] = field(default_factory=list)
    removed_orphans: list[str] = field(default_factory=list)


def reconcile(
    *,
    load_entries_fn: Callable[[], list[Entry]] = load_entries,
    save_entries_fn: Callable[[list[Entry]], None] = save_entries,
    is_hidden_fn: Callable[[str], Optional[bool]] = is_hidden,
    write_desktop_fn: Callable[[Entry], object] = write_desktop_file,
    remove_desktop_fn: Callable[[str], bool] = remove_desktop_file,
    list_slugs_fn: Callable[[], list[str]] = list_managed_slugs,
) -> tuple[list[Entry], SyncReport]:
    entries = load_entries_fn()
    report = SyncReport()
    toml_changed = False

    for entry in entries:
        hidden = is_hidden_fn(entry.slug)
        if hidden is None:
            write_desktop_fn(entry)
            report.regenerated_desktops.append(entry.slug)
            continue
        desktop_enabled = not hidden
        if desktop_enabled != entry.enabled:
            entry.enabled = desktop_enabled
            report.flipped_in_toml.append(entry.slug)
            toml_changed = True

    if toml_changed:
        save_entries_fn(entries)

    toml_slugs = {e.slug for e in entries}
    for slug in list_slugs_fn():
        if slug not in toml_slugs:
            remove_desktop_fn(slug)
            report.removed_orphans.append(slug)

    return entries, report


def ensure_desktop_for_entry(
    entry: Entry,
    *,
    write_fn: Callable[[Entry], object] = write_desktop_file,
) -> None:
    write_fn(entry)

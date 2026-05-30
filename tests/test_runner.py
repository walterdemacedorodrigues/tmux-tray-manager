from tmux_tray.startup.registry import Entry
from tmux_tray.startup.runner import RunningInfo, start_by_slug


def make_entry(slug="james", mode="self-managed", enabled=True) -> Entry:
    return Entry(
        slug=slug,
        name=slug.title(),
        path=f"/home/user/{slug}/run.sh",
        session_name=slug,
        mode=mode,  # type: ignore[arg-type]
        cwd=f"/home/user/{slug}",
        enabled=enabled,
    )


def test_start_by_slug_missing_returns_2():
    executed = []
    rc = start_by_slug(
        "ghost",
        lookup=lambda s: None,
        detector=lambda e: None,
        executor=lambda e: executed.append(e) or 0,
    )
    assert rc == 2
    assert executed == []


def test_start_by_slug_disabled_skips_execution():
    entry = make_entry("james", enabled=False)
    executed = []
    rc = start_by_slug(
        "james",
        lookup=lambda s: entry,
        detector=lambda e: None,
        executor=lambda e: executed.append(e) or 0,
    )
    assert rc == 0
    assert executed == []


def test_start_by_slug_already_running_skips_execution():
    entry = make_entry("james")
    executed = []
    rc = start_by_slug(
        "james",
        lookup=lambda s: entry,
        detector=lambda e: RunningInfo(method="tmux-session", details="session exists"),
        executor=lambda e: executed.append(e) or 0,
    )
    assert rc == 0
    assert executed == []


def test_start_by_slug_executes_when_clear():
    entry = make_entry("james")
    executed = []

    def exec_fake(e):
        executed.append(e)
        return 0

    rc = start_by_slug(
        "james",
        lookup=lambda s: entry,
        detector=lambda e: None,
        executor=exec_fake,
    )
    assert rc == 0
    assert executed == [entry]


def test_start_by_slug_propagates_executor_exit_code():
    entry = make_entry("james")
    rc = start_by_slug(
        "james",
        lookup=lambda s: entry,
        detector=lambda e: None,
        executor=lambda e: 1,
    )
    assert rc == 1

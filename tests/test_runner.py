from tmux_tray.startup.registry import Entry
from tmux_tray.startup.runner import (
    RunningInfo,
    build_self_managed_argv,
    build_tmux_wrapped_command,
    start_by_slug,
)


def make_entry(slug="james", mode="self-managed", enabled=True, command=None) -> Entry:
    return Entry(
        slug=slug,
        name=slug.title(),
        path=f"/home/user/{slug}/run.sh",
        session_name=slug,
        mode=mode,  # type: ignore[arg-type]
        cwd=f"/home/user/{slug}",
        enabled=enabled,
        command=command,
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


def test_build_self_managed_argv_without_command_uses_path():
    entry = make_entry("a", command=None)
    assert build_self_managed_argv(entry) == [entry.path]


def test_build_self_managed_argv_uses_command_when_set():
    entry = make_entry("a", command="python3 /opt/start.py --port 8080")
    assert build_self_managed_argv(entry) == [
        "python3", "/opt/start.py", "--port", "8080",
    ]


def test_build_self_managed_argv_respects_shell_quoting():
    entry = make_entry("a", command="python3 /opt/start.py 'arg with space'")
    assert build_self_managed_argv(entry) == [
        "python3", "/opt/start.py", "arg with space",
    ]


def test_build_tmux_wrapped_command_without_command_uses_path():
    entry = make_entry("a", command=None)
    assert build_tmux_wrapped_command(entry) == entry.path


def test_build_tmux_wrapped_command_uses_command_when_set():
    entry = make_entry("a", command="python3 /opt/start.py")
    assert build_tmux_wrapped_command(entry) == "python3 /opt/start.py"

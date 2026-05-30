from pathlib import Path

from tmux_tray.startup.detection import (
    find_running_pids,
    is_self_tmux,
    scan_xdg_autostart,
)


def test_is_self_tmux_with_new_session(tmp_path):
    p = tmp_path / "run.sh"
    p.write_text("#!/usr/bin/env bash\ntmux new-session -d -s app 'echo hi'\n")
    assert is_self_tmux(p) is True


def test_is_self_tmux_with_attach(tmp_path):
    p = tmp_path / "run.sh"
    p.write_text("#!/bin/sh\ntmux attach -t mysession\n")
    assert is_self_tmux(p) is True


def test_is_self_tmux_with_exec_tmux(tmp_path):
    p = tmp_path / "run.sh"
    p.write_text("#!/bin/sh\nexec tmux\n")
    assert is_self_tmux(p) is True


def test_is_self_tmux_with_has_session(tmp_path):
    p = tmp_path / "run.sh"
    p.write_text("#!/bin/sh\nif ! tmux has-session -t foo; then echo no; fi\n")
    assert is_self_tmux(p) is True


def test_is_self_tmux_negative_plain_script(tmp_path):
    p = tmp_path / "plain.sh"
    p.write_text("#!/bin/sh\necho hello\nls -la\n")
    assert is_self_tmux(p) is False


def test_is_self_tmux_negative_mentions_tmux_in_text(tmp_path):
    p = tmp_path / "plain.sh"
    p.write_text("#!/bin/sh\n# this script does not use tmux\necho done\n")
    assert is_self_tmux(p) is False


def test_is_self_tmux_missing_file(tmp_path):
    assert is_self_tmux(tmp_path / "nonexistent.sh") is False


def test_is_self_tmux_binary_file(tmp_path):
    p = tmp_path / "binary"
    p.write_bytes(b"\x7fELF\x00\x00\x00\x00binary garbage\x00\x00\x00")
    assert is_self_tmux(p) is False


def test_is_self_tmux_oversized_file(tmp_path):
    p = tmp_path / "huge"
    p.write_bytes(b"x" * (2 << 20))
    assert is_self_tmux(p) is False


def _make_fake_proc(root: Path, pid: int, args: list[str]) -> None:
    d = root / str(pid)
    d.mkdir()
    (d / "cmdline").write_bytes(b"\x00".join(a.encode() for a in args) + b"\x00")


def test_find_running_pids_matches_direct_path(tmp_path):
    proc = tmp_path / "proc"
    proc.mkdir()
    target = "/home/user/projects/james/run.sh"
    _make_fake_proc(proc, 100, [target])
    _make_fake_proc(proc, 200, ["/usr/bin/firefox"])
    found = find_running_pids(target, proc_root=proc)
    assert len(found) == 1
    assert found[0].pid == 100


def test_find_running_pids_matches_when_invoked_via_shell(tmp_path):
    proc = tmp_path / "proc"
    proc.mkdir()
    target = "/home/user/projects/james/run.sh"
    _make_fake_proc(proc, 300, ["bash", target, "--flag"])
    found = find_running_pids(target, proc_root=proc)
    assert len(found) == 1
    assert found[0].pid == 300
    assert found[0].matched_arg == target


def test_find_running_pids_no_match(tmp_path):
    proc = tmp_path / "proc"
    proc.mkdir()
    _make_fake_proc(proc, 100, ["/usr/bin/firefox"])
    assert find_running_pids("/home/user/run.sh", proc_root=proc) == []


def test_find_running_pids_skips_nondigit_dirs(tmp_path):
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "cpuinfo").write_text("ignore me")
    (proc / "self").mkdir()
    _make_fake_proc(proc, 100, ["/x"])
    found = find_running_pids("/x", proc_root=proc)
    assert [p.pid for p in found] == [100]


def test_find_running_pids_handles_missing_cmdline(tmp_path):
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "999").mkdir()
    _make_fake_proc(proc, 100, ["/x"])
    found = find_running_pids("/x", proc_root=proc)
    assert [p.pid for p in found] == [100]


def test_find_running_pids_handles_empty_cmdline(tmp_path):
    proc = tmp_path / "proc"
    proc.mkdir()
    d = proc / "888"
    d.mkdir()
    (d / "cmdline").write_bytes(b"")
    _make_fake_proc(proc, 100, ["/x"])
    found = find_running_pids("/x", proc_root=proc)
    assert [p.pid for p in found] == [100]


def test_scan_xdg_autostart_matches_exec(tmp_path):
    target = "/home/user/run.sh"
    (tmp_path / "match.desktop").write_text(
        "[Desktop Entry]\nName=My App\nExec=/home/user/run.sh --foo\n"
    )
    (tmp_path / "nomatch.desktop").write_text(
        "[Desktop Entry]\nName=Other\nExec=/usr/bin/firefox\n"
    )
    matches = scan_xdg_autostart(target, autostart_root=tmp_path)
    assert [p.name for p in matches] == ["match.desktop"]


def test_scan_xdg_autostart_empty_when_no_dir(tmp_path):
    nonexistent = tmp_path / "doesnotexist"
    assert scan_xdg_autostart("/x", autostart_root=nonexistent) == []


def test_scan_xdg_autostart_ignores_exec_substring_outside_exec_line(tmp_path):
    (tmp_path / "name_mention.desktop").write_text(
        "[Desktop Entry]\nName=/home/user/run.sh helper\nExec=/usr/bin/python\n"
    )
    assert scan_xdg_autostart("/home/user/run.sh", autostart_root=tmp_path) == []

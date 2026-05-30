"""Tests for the name/ID derivation heuristic used by the Add wizard.

Pure functions live in startup/naming.py so they can be tested without Qt.
"""

from pathlib import Path

from tmux_tray.startup.naming import (
    derive_name_and_id,
    is_valid_slug,
    slugify,
    suggest_command,
)


def test_generic_stem_uses_parent_dir():
    name, slug = derive_name_and_id(Path("/mnt/X/JAMES/run.sh"))
    assert name == "JAMES"
    assert slug == "james"


def test_generic_stem_with_lowercase_parent():
    name, slug = derive_name_and_id(Path("/home/user/myapp/start.sh"))
    assert name == "Myapp"
    assert slug == "myapp"


def test_non_generic_stem_uses_stem():
    name, slug = derive_name_and_id(Path("/home/user/scripts/backup.sh"))
    assert name == "Backup"
    assert slug == "backup"


def test_non_generic_stem_with_separators():
    name, slug = derive_name_and_id(Path("/home/user/scripts/sync-database.sh"))
    assert name == "Sync Database"
    assert slug == "sync-database"


def test_underscore_in_name_becomes_space():
    name, slug = derive_name_and_id(Path("/home/user/scripts/my_app.sh"))
    assert name == "My App"
    assert slug == "my_app"


def test_uppercase_acronym_preserved():
    name, slug = derive_name_and_id(Path("/x/JAMES/main.sh"))
    assert name == "JAMES"
    assert slug == "james"


def test_no_parent_falls_back_to_stem():
    name, slug = derive_name_and_id(Path("backup.sh"))
    assert name == "Backup"
    assert slug == "backup"


def test_main_in_directory_uses_parent():
    name, slug = derive_name_and_id(Path("/srv/redis-cache/main.sh"))
    assert name == "Redis Cache"
    assert slug == "redis-cache"


def test_slugify_strips_special_chars():
    assert slugify("Hello World!") == "hello-world"
    assert slugify("foo@bar/baz") == "foo-bar-baz"


def test_slugify_empty_or_special_only():
    assert slugify("") == "entry"
    assert slugify("///") == "entry"


def test_slugify_leading_digit_kept():
    assert slugify("2nd-attempt") == "2nd-attempt"


def test_slugify_leading_non_alnum_prefixed():
    assert slugify("--leading") == "e-leading" or slugify("--leading") == "leading"


def test_is_valid_slug_accepts_lowercase_with_hyphen():
    assert is_valid_slug("james") is True
    assert is_valid_slug("my-app-2") is True
    assert is_valid_slug("redis_cache") is True


def test_is_valid_slug_rejects_uppercase_or_spaces():
    assert is_valid_slug("JAMES") is False
    assert is_valid_slug("my app") is False
    assert is_valid_slug("-leading") is False
    assert is_valid_slug("") is False


def test_suggest_command_python():
    assert suggest_command(Path("/srv/app/start.py")) == "python3 /srv/app/start.py"


def test_suggest_command_node():
    assert suggest_command(Path("/srv/app/index.js")) == "node /srv/app/index.js"
    assert suggest_command(Path("/srv/app/index.mjs")) == "node /srv/app/index.mjs"
    assert suggest_command(Path("/srv/app/index.cjs")) == "node /srv/app/index.cjs"


def test_suggest_command_ruby_perl_php():
    assert suggest_command(Path("/x/foo.rb")) == "ruby /x/foo.rb"
    assert suggest_command(Path("/x/foo.pl")) == "perl /x/foo.pl"
    assert suggest_command(Path("/x/foo.php")) == "php /x/foo.php"


def test_suggest_command_shell_returns_none():
    assert suggest_command(Path("/x/run.sh")) is None


def test_suggest_command_binary_returns_none():
    assert suggest_command(Path("/usr/bin/firefox")) is None


def test_suggest_command_unknown_extension_returns_none():
    assert suggest_command(Path("/x/data.txt")) is None


def test_suggest_command_uppercase_extension_still_matches():
    assert suggest_command(Path("/x/START.PY")) == "python3 /x/START.PY"

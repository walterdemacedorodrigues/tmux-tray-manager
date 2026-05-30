"""Pure helpers for deriving entry names/IDs from script paths.

Kept Qt-free so the heuristic is testable without spinning up PySide6.
"""

import re
from pathlib import Path

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_GENERIC_STEMS = {
    "run", "start", "main", "app", "launch", "init", "boot", "go",
    "execute", "exec", "entry", "entrypoint",
}


def is_valid_slug(s: str) -> bool:
    return bool(_SLUG_RE.match(s))


def slugify(text: str) -> str:
    s = text.lower()
    s = re.sub(r"[^a-z0-9_-]+", "-", s).strip("-")
    if not s:
        return "entry"
    if not s[0].isalnum():
        s = "e-" + s
    return s


def derive_name_and_id(path: Path) -> tuple[str, str]:
    """Pick a friendly Name and ID from a script path.

    If the filename is generic (run.sh, start.sh, ...), prefer the parent
    directory name (e.g. /foo/JAMES/run.sh → "JAMES" / "james").
    """
    stem = path.stem
    if stem.lower() in _GENERIC_STEMS and path.parent.name:
        candidate = path.parent.name
    else:
        candidate = stem
    spaced = candidate.replace("_", " ").replace("-", " ").strip() or stem
    pretty = spaced if spaced.isupper() else spaced.title()
    return pretty, slugify(candidate)

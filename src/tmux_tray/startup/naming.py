"""Pure helpers for deriving entry names/IDs from script paths.

Kept Qt-free so the heuristic is testable without spinning up PySide6.
"""

import re
from pathlib import Path
from typing import Optional

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_GENERIC_STEMS = {
    "run", "start", "main", "app", "launch", "init", "boot", "go",
    "execute", "exec", "entry", "entrypoint",
}

# Map of file extensions to interpreter for the "Command" auto-suggestion.
# Files without an entry here (binaries, .sh with shebang) are executed
# directly and need no interpreter prefix.
_INTERPRETERS: dict[str, str] = {
    ".py": "python3",
    ".js": "node",
    ".mjs": "node",
    ".cjs": "node",
    ".rb": "ruby",
    ".pl": "perl",
    ".php": "php",
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


def suggest_command(path: Path) -> Optional[str]:
    """Suggest an interpreter-prefixed command for the given script.

    Returns "<interpreter> <absolute-path>" for known scripting extensions
    (.py, .js, .rb, etc.), or None if the file should run directly via its
    shebang. The absolute path is used so the command works regardless of
    the working directory the user later configures.
    """
    interpreter = _INTERPRETERS.get(path.suffix.lower())
    if interpreter is None:
        return None
    return f"{interpreter} {path}"


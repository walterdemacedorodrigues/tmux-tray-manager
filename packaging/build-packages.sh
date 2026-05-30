#!/usr/bin/env bash
# Build .deb and .rpm from the project's wheel via fpm.
#
# Requirements on the build host:
#   - uv (or `python -m build`) for wheel
#   - fpm (https://fpm.readthedocs.io)
#   - tar, ruby (fpm runtime)
#
# Usage:
#   ./packaging/build-packages.sh         # uses version from pyproject.toml
#   ./packaging/build-packages.sh 0.3.0   # override version
#
# Output: dist/*.deb and dist/*.rpm
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="${1:-$(grep -E '^version\s*=' pyproject.toml | head -1 | cut -d'"' -f2)}"
[ -z "$VERSION" ] && { echo "Could not determine version" >&2; exit 1; }

echo "[build-packages] version=$VERSION"

# 1. Build wheel
uv build --wheel
WHEEL="$(ls -t dist/tmux_tray-${VERSION}-py3-none-any.whl | head -1)"
[ -f "$WHEEL" ] || { echo "Wheel not found" >&2; exit 1; }

# 2. Stage into a temp root reflecting the eventual filesystem layout
STAGING="$(mktemp -d)"
trap "rm -rf '$STAGING'" EXIT

python3 -m installer --destdir="$STAGING" --prefix=/usr "$WHEEL"
install -Dm644 LICENSE "$STAGING/usr/share/licenses/tmux-tray/LICENSE" 2>/dev/null \
  || install -Dm644 LICENSE "$STAGING/usr/share/doc/tmux-tray/LICENSE"

[ -x "$STAGING/usr/bin/tmux-tray" ] || { echo "installer didn't produce /usr/bin/tmux-tray" >&2; exit 1; }

DESC="System tray monitor for tmux sessions (KDE/Wayland)"
URL="https://github.com/walterdemacedorodrigues/tmux-tray-manager"
MAINT="Walter Rodrigues <walterdemacedorodrigues@gmail.com>"

# 3. .deb (Debian/Ubuntu/Mint)
fpm -s dir -t deb -n tmux-tray -v "$VERSION" \
    --architecture all \
    --maintainer "$MAINT" \
    --description "$DESC" \
    --url "$URL" \
    --license MIT \
    --depends "python3 (>= 3.11)" \
    --depends "tmux" \
    --depends "python3-pyside6.qtwidgets" \
    --deb-no-default-config-files \
    --force \
    -p dist/ \
    -C "$STAGING" usr

# 4. .rpm (Fedora/openSUSE/RHEL)
fpm -s dir -t rpm -n tmux-tray -v "$VERSION" \
    --architecture noarch \
    --maintainer "$MAINT" \
    --description "$DESC" \
    --url "$URL" \
    --license MIT \
    --depends "python3 >= 3.11" \
    --depends "tmux" \
    --depends "python3-pyside6" \
    --force \
    -p dist/ \
    -C "$STAGING" usr

echo "[build-packages] done:"
ls -1 dist/*.deb dist/*.rpm 2>/dev/null | sed 's/^/  /'

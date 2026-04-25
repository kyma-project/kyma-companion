#!/usr/bin/env bash
# Usage: update-dep.sh <subproject_dir> <pkg_spec> [extra_poetry_add_args...]
# pkg_spec: package name optionally with version (e.g. "mypy" or "mypy@latest" or "mypy@^1.2")
# Defaults to "<pkg>@latest" when no version suffix is given.
# Extra args (e.g. --group test) are passed through to poetry add.
set -euo pipefail

SUBPROJECT_DIR="$1"
PKG_SPEC="$2"
shift 2
EXTRA_ARGS=("$@")

# Extract bare package name for poetry show
PKG="${PKG_SPEC%%@*}"

# Default to @latest if no version suffix provided
if [[ "$PKG_SPEC" != *@* ]]; then
  PKG_SPEC="${PKG_SPEC}@latest"
fi

cd "$SUBPROJECT_DIR"

OLD=$(poetry show "$PKG" --no-ansi 2>/dev/null | grep "^ *version" | awk '{print $NF}')
poetry add "$PKG_SPEC" "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"
NEW=$(poetry show "$PKG" --no-ansi 2>/dev/null | grep "^ *version" | awk '{print $NF}')
poetry run poe pre-commit-check
git add -A
git commit -m "deps: update ${PKG} from v${OLD} to v${NEW}"

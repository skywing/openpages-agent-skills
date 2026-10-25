#!/usr/bin/env bash
# Create/refresh the project virtual environment in ./.venv (run on your Mac).
#   bash setup_venv.sh              create/update; rebuilds automatically if .venv has the wrong Python
#   bash setup_venv.sh --recreate   force rebuild
#   PYTHON=/path/to/python3.12 bash setup_venv.sh   use an explicit interpreter
# Target version comes from .python-version (major.minor, e.g. 3.12).
set -euo pipefail
cd "$(dirname "$0")"
WANT="$(tr -d ' \n' < .python-version 2>/dev/null || echo 3.12)"

ver() { "$1" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null; }

find_python() {
  if [ -n "${PYTHON:-}" ]; then echo "$PYTHON"; return; fi
  # Non-interactive bash does not load ~/.zshrc (pyenv/aliases), so look in the usual places explicitly.
  local c
  for c in \
    "python$WANT" \
    "/opt/homebrew/bin/python$WANT" "/usr/local/bin/python$WANT" \
    "/Library/Frameworks/Python.framework/Versions/$WANT/bin/python3" \
    "$HOME/.pyenv/versions/$(ls "$HOME/.pyenv/versions" 2>/dev/null | grep -E "^$WANT(\.|$)" | sort -V | tail -1)/bin/python3" \
    "$HOME/.local/bin/python$WANT" \
    "/opt/homebrew/bin/python3" "python3"; do
    if command -v "$c" >/dev/null 2>&1 && [ "$(ver "$(command -v "$c")")" = "$WANT" ]; then command -v "$c"; return; fi
  done
  return 1
}

PY="$(find_python)" || {
  echo "Python $WANT not found. Found instead:"; for p in $(which -a python3 python3.1{0,1,2,3} 2>/dev/null | sort -u); do echo "  $p -> $(ver "$p")"; done
  echo "Install it (brew install python@$WANT) or run: PYTHON=/path/to/python$WANT bash setup_venv.sh"; exit 1; }
HAVE="$(ver "$PY")"
echo "Using $PY (Python $HAVE)"

if [ -x .venv/bin/python ]; then
  CUR="$(ver .venv/bin/python || echo none)"
  if [ "${1:-}" = "--recreate" ] || [ "$CUR" != "$HAVE" ]; then
    echo "Rebuilding .venv (current: $CUR, wanted: $HAVE)"; rm -rf .venv
  fi
fi
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip freeze > requirements.lock.txt
echo "OK: $(.venv/bin/python --version) at $(pwd)/.venv"
echo "Activate for interactive use:  source .venv/bin/activate"

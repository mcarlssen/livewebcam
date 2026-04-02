#!/usr/bin/env bash
# Install LiveWebcam for the current user (pipx if available, else a project .venv).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if command -v pipx >/dev/null 2>&1; then
  echo "Installing with pipx (recommended — isolated app + deps)…"
  pipx install "$ROOT"
  echo ""
  echo "Run:  livewebcam"
  echo "Ensure ~/.local/bin is on PATH (pipx default)."
else
  echo "pipx not found; using a local venv at $ROOT/.venv"
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/python" -m pip install -U pip setuptools wheel
  "$ROOT/.venv/bin/pip" install "$ROOT"
  echo ""
  echo "Run:  $ROOT/.venv/bin/livewebcam"
  echo "Or:   source $ROOT/.venv/bin/activate && livewebcam"
fi

echo ""
echo "Hooks (optional):"
echo "  mkdir -p ~/bin"
echo "  cp \"$ROOT/examples/webcam_activated.sh\" \"$ROOT/examples/webcam_deactivated.sh\" ~/bin/"
echo "  chmod +x ~/bin/webcam_activated.sh ~/bin/webcam_deactivated.sh"

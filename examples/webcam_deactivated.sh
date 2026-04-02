#!/usr/bin/env bash
# Example: turn blink(1) off when the webcam is idle.
# Copy to ~/bin/webcam_deactivated.sh and chmod +x.

set -euo pipefail
if command -v blink1-tool >/dev/null 2>&1; then
  echo "blink1-tool: off (webcam off)"
  blink1-tool --off -q || blink1-tool -m 0 --off -q
else
  echo "blink1-tool not found on PATH" >&2
  exit 1
fi

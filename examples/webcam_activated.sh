#!/usr/bin/env bash
# Example: drive a ThingM blink(1) when the webcam turns on (install: brew install blink1).
# Copy to ~/bin/webcam_activated.sh and chmod +x.

set -euo pipefail
if command -v blink1-tool >/dev/null 2>&1; then
  echo "blink1-tool: red (webcam on)"
  blink1-tool -m 2000 --red -q
else
  echo "blink1-tool not found on PATH — brew install blink1 or add repo bin to PATH" >&2
  exit 1
fi

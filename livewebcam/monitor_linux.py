"""Linux: uvcvideo kernel module use count (same idea as original livewebcam)."""

from __future__ import annotations

import logging
import subprocess

_log = logging.getLogger(__name__)


def is_camera_active() -> bool:
    """True if uvcvideo module refcount is non-zero."""
    try:
        p = subprocess.run(
            ["sh", "-c", "lsmod | grep '^uvcvideo' | awk '{print $3}'"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        _log.debug("linux uvcvideo probe failed: %s", e)
        return False
    val = (p.stdout or "").strip()
    active = val not in ("", "0")
    _log.debug("linux uvcvideo refcount=%r active=%s", val, active)
    return active

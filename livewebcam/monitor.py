"""Platform dispatch for camera-active detection."""

from __future__ import annotations

import sys


def is_camera_active() -> bool:
    if sys.platform.startswith("linux"):
        from livewebcam.monitor_linux import is_camera_active as _fn

        return _fn()
    if sys.platform == "darwin":
        from livewebcam.monitor_darwin import is_camera_active as _fn

        return _fn()
    raise RuntimeError(f"Unsupported platform: {sys.platform}")

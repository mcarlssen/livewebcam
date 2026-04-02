"""macOS: lsof heuristic for camera-related open files (USBVDC, AppleCamera, …)."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import threading
from typing import List, Optional, Tuple

_log = logging.getLogger(__name__)

# Prefer system lsof on macOS (consistent PATH when launched from GUI / .app).
def _lsof_executable() -> str:
    p = "/usr/sbin/lsof"
    if sys.platform == "darwin" and os.path.isfile(p) and os.access(p, os.X_OK):
        return p
    return "lsof"

# Substrings matched case-insensitively on full lsof lines (after noise filter).
LSOF_MARKERS: Tuple[str, ...] = (
    "AppleCamera",
    "USBVDC",
    "VDCAssistant",
    "cmiodalassistants",
    "iSight",
    "UVC",
    "CMIO",
)

_NOISE_SUBSTRINGS: Tuple[str, ...] = (
    "CMIOUnits.bundle",
    "CMIOBaseUnits.bundle",
)

LOG_PREDICATE = (
    '(eventMessage CONTAINS "AVCaptureSessionDidStartRunningNotification") OR '
    '(eventMessage CONTAINS "AVCaptureSessionDidStopRunningNotification") OR '
    '(eventMessage CONTAINS "kCameraStreamStart") OR '
    '(eventMessage CONTAINS "kCameraStreamStop") OR '
    '(eventMessage CONTAINS "Cameras changed to")'
)


def _is_noise_line(line: str) -> bool:
    return any(n in line for n in _NOISE_SUBSTRINGS)


def match_lines_lsof(text: str, markers: Tuple[str, ...]) -> List[str]:
    out: List[str] = []
    for line in text.splitlines():
        if _is_noise_line(line):
            continue
        low = line.lower()
        for m in markers:
            if m.lower() in low:
                out.append(line)
                break
    return out


def lsof_text() -> str:
    global _warned_short_lsof
    exe = _lsof_executable()
    try:
        p = subprocess.run(
            [exe, "-n"],
            capture_output=True,
            text=True,
            timeout=60,
            errors="replace",
        )
        if p.stderr:
            _log.debug("lsof stderr (%s): %s", exe, p.stderr[:800])
        if p.returncode != 0 and not (p.stdout or ""):
            _log.warning("lsof exit %s (%s)", p.returncode, exe)
        raw = p.stdout or ""
        nlines = len(raw.splitlines())
        _log.debug("lsof raw: %s bytes, %s lines (exe=%s)", len(raw), nlines, exe)
        return raw
    except FileNotFoundError:
        _log.error("lsof not found (tried %s)", exe)
        return ""
    except subprocess.TimeoutExpired:
        _log.error("lsof timed out (%s)", exe)
        return ""
    except OSError as e:
        _log.error("lsof failed (%s): %s", exe, e)
        return ""


def probe_lsof(markers: Tuple[str, ...]) -> Tuple[bool, int, List[str]]:
    raw = lsof_text()
    lines = match_lines_lsof(raw, markers)
    return (len(lines) > 0, len(lines), lines)


def _parse_log_line_for_state(line: str) -> Optional[bool]:
    if "AVCaptureSessionDidStopRunningNotification" in line or "kCameraStreamStop" in line:
        return False
    if "AVCaptureSessionDidStartRunningNotification" in line or "kCameraStreamStart" in line:
        return True
    if "Cameras changed to" in line:
        if re.search(r"Cameras changed to\s*\[\s*\]", line):
            return False
        return True
    return None


def seed_state_from_log(seconds: str = "60s") -> Optional[bool]:
    try:
        p = subprocess.run(
            [
                "log",
                "show",
                "--last",
                seconds,
                "--style",
                "compact",
                "--predicate",
                LOG_PREDICATE,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if p.returncode != 0:
        return None
    lines = [ln for ln in p.stdout.splitlines() if ln.strip()]
    for line in reversed(lines):
        st = _parse_log_line_for_state(line)
        if st is not None:
            return st
    return None


def run_log_stream(state: List[Optional[bool]], stop: threading.Event) -> None:
    try:
        proc = subprocess.Popen(
            ["log", "stream", "--style", "compact", "--predicate", LOG_PREDICATE],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
    except (FileNotFoundError, OSError) as e:
        print(f"log stream failed: {e}", file=sys.stderr)
        return
    assert proc.stdout is not None
    try:
        while not stop.is_set():
            line = proc.stdout.readline()
            if not line:
                break
            st = _parse_log_line_for_state(line)
            if st is not None:
                state[0] = st
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


_log_state: List[Optional[bool]] = [None]
_log_stop: Optional[threading.Event] = None
_log_thread: Optional[threading.Thread] = None


def _ensure_log_thread() -> None:
    global _log_stop, _log_thread
    if _log_thread is not None and _log_thread.is_alive():
        return
    _log_state[0] = seed_state_from_log()
    _log_stop = threading.Event()
    _log_thread = threading.Thread(
        target=run_log_stream,
        args=(_log_state, _log_stop),
        daemon=True,
    )
    _log_thread.start()


def is_camera_active() -> bool:
    """
    True if webcam appears in use (heuristic).

    Default on macOS: **hybrid** — combine `lsof` with Unified Log (same idea as
    `camera_probe_macos.py --method both`). `lsof` alone often returns **zero**
    matches when the app lacks Full Disk Access (other processes' FDs are hidden).

    Final result is **lsof OR unified log** (either may indicate active).

    Set ``LIVEWEBCAM_MACOS_USE_LOG=0`` to use **lsof only** (matches old behavior).
    """
    # Default ON; set LIVEWEBCAM_MACOS_USE_LOG=0 to disable unified log.
    use_log = os.environ.get("LIVEWEBCAM_MACOS_USE_LOG", "1").lower() not in (
        "0",
        "false",
        "no",
    )
    active_lsof, n, lines = probe_lsof(LSOF_MARKERS)
    _log.debug(
        "darwin lsof: active=%s match_count=%s sample_lines=%s",
        active_lsof,
        n,
        len(lines),
    )
    if lines and _log.isEnabledFor(logging.DEBUG):
        for i, ln in enumerate(lines[:5]):
            _log.debug("  lsof match %s: %s", i + 1, ln[:200])
        if len(lines) > 5:
            _log.debug("  ... and %s more lines", len(lines) - 5)

    if not use_log:
        _log.debug("darwin result (lsof only): %s", active_lsof)
        return active_lsof

    _ensure_log_thread()
    log_val = _log_state[0]
    # OR: trust either signal — lsof may be blind without FDA; log may lag or miss.
    out = active_lsof or (bool(log_val) if log_val is not None else False)
    _log.debug(
        "darwin result (hybrid OR): lsof=%s log_state=%s -> %s",
        active_lsof,
        log_val,
        out,
    )
    return out

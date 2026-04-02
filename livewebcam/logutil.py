"""Logging: stderr + optional file. Set LIVEWEBCAM_DEBUG=1 or pass --debug."""

from __future__ import annotations

import logging
import os
import sys


def setup_logging() -> None:
    debug = os.environ.get("LIVEWEBCAM_DEBUG", "").lower() in ("1", "true", "yes")
    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    log = logging.getLogger("livewebcam")
    log.handlers.clear()
    log.setLevel(level)
    log.propagate = False

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(level)
    sh.setFormatter(logging.Formatter(fmt, datefmt))
    log.addHandler(sh)

    path = os.environ.get("LIVEWEBCAM_LOGFILE", "").strip()
    if path:
        expanded = os.path.expanduser(path)
        try:
            fh = logging.FileHandler(expanded, encoding="utf-8")
            fh.setLevel(level)
            fh.setFormatter(logging.Formatter(fmt, datefmt))
            log.addHandler(fh)
            log.info("Also logging to file: %s", expanded)
        except OSError as e:
            sys.stderr.write(f"livewebcam: could not open LIVEWEBCAM_LOGFILE {expanded}: {e}\n")

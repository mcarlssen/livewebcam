#!/usr/bin/env python3
"""
Phase-0 probe: CLI wrapper around livewebcam.monitor_darwin (tuning / debugging).

Usage:
  python3 scripts/camera_probe_macos.py
  python3 scripts/camera_probe_macos.py --method stream
  python3 scripts/camera_probe_macos.py --method lsof -v
  python3 scripts/camera_probe_macos.py --dump
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
from datetime import datetime

from livewebcam.monitor_darwin import (
    LOG_PREDICATE,
    LSOF_MARKERS,
    lsof_text,
    probe_lsof,
    run_log_stream,
    seed_state_from_log,
)

# mmap noise: matches CoreMediaIO plugin binaries, not a live stream.
_NOISE_KEYS = (
    "gather",
    "camera",
    "cmio",
    "vdc",
    "applecamera",
    "uvc",
    "isight",
    "facetime",
)


def dump_lsof_snippets() -> None:
    raw = lsof_text()
    print("--- lines containing (case-insensitive):", ", ".join(_NOISE_KEYS), "---")
    n = 0
    for line in raw.splitlines():
        low = line.lower()
        if any(k in low for k in _NOISE_KEYS):
            print(line)
            n += 1
    print(f"--- total {n} lines (from full lsof) ---", file=sys.stderr)


def main() -> int:
    if sys.platform != "darwin":
        print("This script is for macOS only.", file=sys.stderr)
        return 2

    ap = argparse.ArgumentParser(description="Poll for webcam activity (heuristic).")
    ap.add_argument(
        "-n",
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between polls (default: 1)",
    )
    ap.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print up to 5 matching lsof lines each tick (lsof / both)",
    )
    ap.add_argument(
        "--only-changes",
        action="store_true",
        help="Print only when ACTIVE/INACTIVE state changes",
    )
    ap.add_argument(
        "--method",
        choices=("lsof", "stream", "both"),
        default="both",
        help="lsof only; unified log stream only; or hybrid (default)",
    )
    ap.add_argument(
        "--dump",
        action="store_true",
        help="Print lsof lines mentioning camera-related keywords, then exit",
    )
    args = ap.parse_args()

    if args.dump:
        dump_lsof_snippets()
        return 0

    markers = LSOF_MARKERS
    log_state: list[bool | None] = [None]
    stop_event = threading.Event()
    stream_thread: threading.Thread | None = None

    if args.method in ("stream", "both"):
        seeded = seed_state_from_log()
        log_state[0] = seeded
        if seeded is not None:
            print(f"Seeded from log show: {'ACTIVE' if seeded else 'INACTIVE'}", file=sys.stderr)
        else:
            print(
                "No recent camera events in log (60s); stream will set state on next on/off.",
                file=sys.stderr,
            )
        stream_thread = threading.Thread(
            target=run_log_stream,
            args=(log_state, stop_event),
            daemon=True,
        )
        stream_thread.start()

    prev: bool | None = None
    print("camera_probe_macos — Ctrl+C to quit", file=sys.stderr)
    print(f"method={args.method}  lsof markers: {markers}", file=sys.stderr)
    print(f"LOG_PREDICATE={LOG_PREDICATE[:80]}...", file=sys.stderr)

    try:
        while True:
            active_lsof = False
            n_lsof = 0
            lines: list[str] = []
            if args.method in ("lsof", "both"):
                active_lsof, n_lsof, lines = probe_lsof(markers)

            active_log = log_state[0]
            if args.method == "lsof":
                active = active_lsof
            elif args.method == "stream":
                active = bool(active_log) if active_log is not None else False
            else:
                if active_log is not None:
                    active = active_log
                else:
                    active = active_lsof

            ts = datetime.now().isoformat(timespec="seconds")
            if not args.only_changes or prev is None or active != prev:
                status = "ACTIVE" if active else "INACTIVE"
                extra = ""
                if args.method == "both":
                    extra = f"  lsof={active_lsof}({n_lsof}) log={active_log}"
                elif args.method == "lsof":
                    extra = f"  matches={n_lsof}"
                elif args.method == "stream":
                    extra = f"  log_state={active_log}"
                print(f"{ts}  {status}{extra}")
                if args.verbose and lines and args.method in ("lsof", "both"):
                    for ln in lines[:5]:
                        print(f"    {ln}")
                    if len(lines) > 5:
                        print(f"    ... and {len(lines) - 5} more")
                prev = active
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("", file=sys.stderr)
        return 0
    finally:
        stop_event.set()
        if stream_thread is not None:
            stream_thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())

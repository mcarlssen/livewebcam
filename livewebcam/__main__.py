"""Entry: python3 -m livewebcam

Options (parsed before wx starts):
  --debug       Set LIVEWEBCAM_DEBUG=1 (per-poll logs, monitor detail).
  --logfile PATH Append logs to this file (also sets LIVEWEBCAM_LOGFILE).
"""

from __future__ import annotations

import argparse
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="LiveWebcam menu bar monitor",
        add_help=True,
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Verbose logging (same as LIVEWEBCAM_DEBUG=1)",
    )
    parser.add_argument(
        "--logfile",
        type=str,
        default=None,
        metavar="PATH",
        help="Append logs to this file (e.g. ~/Library/Logs/livewebcam.log)",
    )
    args, wx_argv = parser.parse_known_args()
    sys.argv = [sys.argv[0]] + wx_argv

    if args.debug:
        os.environ["LIVEWEBCAM_DEBUG"] = "1"
    if args.logfile:
        os.environ["LIVEWEBCAM_LOGFILE"] = args.logfile

    try:
        from livewebcam.logutil import setup_logging

        setup_logging()
        from livewebcam.ui import run_app
    except ImportError as e:
        print("Install wxPython: pip install wxpython", file=sys.stderr)
        print(e, file=sys.stderr)
        return 1
    run_app()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

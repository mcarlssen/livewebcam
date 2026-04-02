"""wxPython menu bar / system tray UI."""

from __future__ import annotations

import logging
import os
import pathlib
import shutil
import subprocess
import sys
import time
from datetime import datetime

import wx
import wx.adv

from livewebcam.monitor import is_camera_active

logger = logging.getLogger(__name__)


def _make_tray_icon(active: bool) -> wx.Icon:
    """
    Wide pill with small label: "webcam ON" / "webcam OFF".
    macOS may still apply template styling to menu bar images; text keeps states distinct.
    """
    label = "CAM" if active else "off"
    pad_x, pad_y = 6, 3
    max_w = 140 if sys.platform == "darwin" else 170
    pt = 8 if sys.platform == "darwin" else 9

    def _font(sz: int) -> wx.Font:
        try:
            return wx.Font(wx.FontInfo(sz).Bold().Family(wx.FONTFAMILY_DEFAULT))
        except (TypeError, AttributeError):
            return wx.Font(
                sz,
                wx.FONTFAMILY_DEFAULT,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_BOLD,
            )

    measure = wx.Bitmap(1, 1)
    mdc = wx.MemoryDC(measure)
    tw, th = 0, 0
    font = _font(pt)
    while pt >= 6:
        mdc.SelectObject(measure)
        mdc.SetFont(font)
        tw, th = mdc.GetTextExtent(label)
        if tw + pad_x * 2 <= max_w:
            break
        pt -= 1
        font = _font(pt)
    mdc.SelectObject(wx.NullBitmap)

    w = min(max_w, int(tw + pad_x * 2))
    h = max(20 if sys.platform == "darwin" else 22, int(th + pad_y * 2))

    bmp = wx.Bitmap(w, h)
    dc = wx.MemoryDC(bmp)
    try:
        if active:
            bg = wx.Colour(195, 48, 48)
            fg = wx.Colour(255, 255, 255)
            border = wx.Colour(120, 25, 25)
        else:
            bg = wx.Colour(88, 88, 92)
            fg = wx.Colour(245, 245, 245)
            border = wx.Colour(45, 45, 48)
        dc.SetBackground(wx.Brush(bg))
        dc.Clear()
        dc.SetFont(font)
        dc.SetBrush(wx.Brush(bg))
        dc.SetPen(wx.Pen(border, width=1))
        radius = max(4, h // 2 - 1)
        if hasattr(dc, "DrawRoundedRectangle"):
            dc.DrawRoundedRectangle(0, 0, w, h, radius)
        else:
            dc.DrawRectangle(0, 0, w, h)
        dc.SetTextForeground(fg)
        tx = max(pad_x, (w - tw) // 2)
        ty = (h - th) // 2
        dc.DrawText(label, tx, ty)
    finally:
        dc.SelectObject(wx.NullBitmap)
    icon = wx.Icon()
    icon.CopyFromBitmap(bmp)
    return icon


def _repo_bin_dir() -> pathlib.Path:
    """livewebcam/package -> repo root."""
    return pathlib.Path(__file__).resolve().parent.parent / "bin"


def _log_startup_diagnostics() -> None:
    logger.info("platform=%s argv=%s", sys.platform, sys.argv)
    if sys.platform == "darwin":
        logger.info(
            "macOS: camera detection defaults to hybrid (lsof OR unified log). "
            "Set LIVEWEBCAM_MACOS_USE_LOG=0 for lsof-only (matches old probe without --method both). "
            "If lsof shows match_count=0, add Full Disk Access for Terminal or this app."
        )
    act = os.path.expanduser("~/bin/webcam_activated.sh")
    deact = os.path.expanduser("~/bin/webcam_deactivated.sh")
    for label, p in (("activated", act), ("deactivated", deact)):
        if os.path.isfile(p) and os.access(p, os.X_OK):
            logger.info("hook OK: %s -> %s", label, p)
        elif os.path.isfile(p):
            logger.warning("hook not executable: %s (chmod +x?)", p)
        else:
            logger.warning(
                "hook missing: %s — copy examples/webcam_%s.sh and chmod +x",
                p,
                label,
            )

    w = shutil.which("blink1-tool")
    if w:
        logger.info("blink1-tool on PATH: %s", w)
    else:
        logger.warning(
            "blink1-tool not found on PATH — add brew install blink1 or export PATH to include the repo bin/ directory",
        )
    rb = _repo_bin_dir() / "blink1-tool"
    if rb.is_file():
        logger.info("found repo copy at %s (ensure PATH includes that directory for hooks)", rb)


def _run_hook(name: str) -> None:
    path = os.path.expanduser(os.path.join("~/bin", name))
    if not os.path.isfile(path):
        logger.warning("hook not run — file missing: %s", path)
        return
    if not os.access(path, os.X_OK):
        logger.warning("hook not run — not executable: %s", path)
        return
    logger.info("running hook: %s", path)
    try:
        r = subprocess.run(
            [path],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ},
        )
        logger.info("hook %s finished exit_code=%s", name, r.returncode)
        if r.stdout or r.stderr:
            chunks = []
            if r.stdout:
                chunks.append("[stdout]\n" + r.stdout.rstrip()[:4000])
            if r.stderr:
                chunks.append("[stderr]\n" + r.stderr.rstrip()[:4000])
            logger.info("hook %s output:\n%s", name, "\n".join(chunks))
        if r.returncode != 0:
            logger.warning("hook %s exited non-zero: %s", name, r.returncode)
    except subprocess.TimeoutExpired:
        logger.error("hook timed out: %s", path)
    except OSError as e:
        logger.error("hook failed: %s: %s", path, e)


def create_menu_item(menu, label, func, icon=None):
    item = wx.MenuItem(menu, -1, label)
    if icon:
        img = wx.Image(icon, wx.BITMAP_TYPE_ANY).Scale(32, 32)
        item.SetBitmap(wx.Bitmap(img))
    menu.Bind(wx.EVT_MENU, func, id=item.GetId())
    menu.Append(item)
    return item


class TaskBarIcon(wx.adv.TaskBarIcon):
    HEARTBEAT_INTERVAL = 30

    def __init__(self, frame: wx.Frame):
        super().__init__()
        self.frame = frame
        self._last_active: bool | None = None
        self._poll_count = 0
        self._set_icon_visual(False, initial=True)
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.on_about)
        self._timer = wx.Timer(self.frame)
        self.frame.Bind(wx.EVT_TIMER, self._on_timer, self._timer)
        self._timer.Start(1000)

    def _set_icon_visual(self, active: bool, *, initial: bool = False) -> None:
        label = "webcam ON" if active else "webcam OFF"
        logger.debug("SetIcon pill %s", label)
        icon = _make_tray_icon(active)
        tip = f"LiveWebcam — {label}"
        if sys.platform == "darwin" and hasattr(self, "RemoveIcon"):
            try:
                self.RemoveIcon()
            except Exception as e:
                logger.debug("RemoveIcon: %s", e)
        self.SetIcon(icon, tooltip=tip)
        if initial:
            logger.info("menu bar icon initialized: %s", label)

    def _apply_state(self, active: bool) -> None:
        self._set_icon_visual(active)
        if self._last_active is None:
            self._last_active = active
            logger.info("first poll: camera_active=%s", active)
            if active:
                logger.info("%s activated (initial)", datetime.now().isoformat())
                _run_hook("webcam_activated.sh")
            return
        if active == self._last_active:
            return
        self._last_active = active
        if active:
            logger.info("%s STATE -> active (camera on)", datetime.now().isoformat())
            _run_hook("webcam_activated.sh")
        else:
            logger.info("%s STATE -> inactive (camera off)", datetime.now().isoformat())
            _run_hook("webcam_deactivated.sh")

    def _on_timer(self, _evt: wx.TimerEvent) -> None:
        self._poll_count += 1
        t0 = time.monotonic()
        try:
            active = is_camera_active()
            dt = time.monotonic() - t0
            logger.debug(
                "poll #%s is_camera_active() -> %s (%.2fs)",
                self._poll_count,
                active,
                dt,
            )
            if dt > 3.0:
                logger.warning("slow poll: is_camera_active() took %.1fs", dt)
            self._apply_state(active)
            if self._poll_count % self.HEARTBEAT_INTERVAL == 0:
                logger.info(
                    "heartbeat poll #%s camera_active=%s",
                    self._poll_count,
                    active,
                )
        except Exception as e:
            logger.exception("poll error: %s", e)

    def CreatePopupMenu(self) -> wx.Menu:
        menu = wx.Menu()
        create_menu_item(menu, "About", self.on_about)
        menu.AppendSeparator()
        create_menu_item(menu, "Exit", self.on_exit)
        return menu

    def on_about(self, _event) -> None:
        wx.MessageDialog(
            None,
            "LiveWebcam runs in the menu bar and watches for webcam activity.\n\n"
            "When the state changes it runs (if present and executable):\n"
            "  ~/bin/webcam_activated.sh\n"
            "  ~/bin/webcam_deactivated.sh\n\n"
            "Verbose logging: run with --debug or set LIVEWEBCAM_DEBUG=1.\n"
            "Log file: --logfile ~/Library/Logs/livewebcam.log\n\n"
            "Only put scripts you trust in ~/bin.",
            "LiveWebcam",
            wx.OK | wx.ICON_INFORMATION,
        ).ShowModal()

    def on_exit(self, _event) -> None:
        if hasattr(self, "_timer"):
            self._timer.Stop()
        wx.CallAfter(self.Destroy)
        self.frame.Close()


class App(wx.App):
    def OnInit(self) -> bool:
        _log_startup_diagnostics()
        if sys.stderr.isatty():
            logger.info(
                "stderr is a TTY — you should see logs here. "
                "Launched from Finder? Use --logfile or Console.app.",
            )
        frame = wx.Frame(None)
        self.SetTopWindow(frame)
        TaskBarIcon(frame)
        return True


def run_app() -> None:
    app = App(False)
    app.MainLoop()

"""
browser_cursor.py
-----------------
Swaps the Windows system cursor to a crosshair while the agent is in control,
then restores the original on exit.

Uses ctypes only — no third-party dependency.

Usage:
    with agent_cursor():
        # agent does browser work here
        ...
    # cursor restored automatically
"""

import contextlib
import ctypes

from core.logger import logger

# Windows cursor constants
_OCR_NORMAL  = 32512   # the default arrow cursor we replace
_IDC_CROSS   = 32515   # crosshair — visually distinct, always available

_user32 = ctypes.windll.user32


def _load_cross_cursor() -> int:
    """Load the built-in Windows crosshair cursor and return its handle."""
    handle = _user32.LoadCursorW(None, _IDC_CROSS)
    if not handle:
        raise OSError("LoadCursorW failed")
    # CopyIcon makes the handle owned by us so SetSystemCursor can consume it
    copy = _user32.CopyIcon(handle)
    if not copy:
        raise OSError("CopyIcon failed")
    return copy


def set_agent_cursor() -> bool:
    """
    Replace the normal arrow cursor with a crosshair.
    Returns True on success, False if the OS call failed (e.g. locked session).
    """
    try:
        handle = _load_cross_cursor()
        result = _user32.SetSystemCursor(handle, _OCR_NORMAL)
        if not result:
            logger.warning("SetSystemCursor returned 0 — cursor not changed")
            return False
        logger.info("Agent cursor set (crosshair)")
        return True
    except Exception as exc:
        logger.warning(f"Could not set agent cursor: {exc}")
        return False


def restore_cursor() -> None:
    """
    Restore all system cursors to the Windows default scheme.
    SPI_SETCURSORS = 0x0057, SPIF_SENDCHANGE | SPIF_UPDATEINIFILE = 0x0003
    """
    try:
        _user32.SystemParametersInfoW(0x0057, 0, None, 0x0003)
        logger.info("System cursor restored")
    except Exception as exc:
        logger.warning(f"Could not restore cursor: {exc}")


@contextlib.contextmanager
def agent_cursor():
    """
    Context manager: set the agent cursor on enter, restore on exit.

    If the cursor swap fails (e.g. running headless), execution continues
    normally — the cursor indicator is best-effort.
    """
    set_agent_cursor()
    try:
        yield
    finally:
        restore_cursor()

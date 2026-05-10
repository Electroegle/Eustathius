"""
browser_detector.py
-------------------
Auto-detects installed browsers on Windows.
Priority: Chrome -> Edge -> Firefox -> Playwright bundled Chromium (fallback).
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class BrowserInfo:
    name: str
    channel: str | None       # playwright launch channel (preferred)
    executable: str | None    # fallback path if no channel


_CANDIDATES: list[tuple[str, str, list[str]]] = [
    (
        "Chrome", "chrome",
        [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            str(Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe"),
        ],
    ),
    (
        "Edge", "msedge",
        [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
    ),
    (
        "Firefox", "firefox",
        [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        ],
    ),
]


def detect_browser() -> BrowserInfo:
    """Return the first browser found; falls back to Playwright bundled Chromium."""
    for name, channel, paths in _CANDIDATES:
        for path in paths:
            if Path(path).exists():
                return BrowserInfo(name=name, channel=channel, executable=path)
    return BrowserInfo(name="Chromium (bundled)", channel=None, executable=None)


def list_available_browsers() -> list[BrowserInfo]:
    """Return every browser found on this machine."""
    found = []
    for name, channel, paths in _CANDIDATES:
        for path in paths:
            if Path(path).exists():
                found.append(BrowserInfo(name=name, channel=channel, executable=path))
                break
    return found or [BrowserInfo(name="Chromium (bundled)", channel=None, executable=None)]

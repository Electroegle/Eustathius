"""
theme.py
--------
Single source of truth for Eustathius UI colours and styles.
"""

from rich.theme import Theme
from rich.console import Console

# Palette
PRIMARY = "rgb(74,144,226)"     # blue: labels, borders, accents
BRIGHT = "rgb(164,207,255)"     # light blue: important values
MUTED = "rgb(83,101,120)"       # blue-grey: dividers and secondary chrome
DIM_TEXT = "rgb(132,147,163)"   # grey-blue: hints and timestamps
BODY = "rgb(224,232,240)"       # soft white: answer body
ERR = "rgb(224,86,86)"          # red: errors only
WARN = "rgb(235,184,92)"        # amber: warnings
SUCCESS = "rgb(95,196,139)"     # green: success

EU_THEME = Theme({
    "primary": PRIMARY,
    "bright": BRIGHT,
    "muted": MUTED,
    "dim_text": DIM_TEXT,
    "body": BODY,
    "err": ERR,
    "warn": WARN,
    "label": f"bold {PRIMARY}",
    "value": BRIGHT,
    "hint": DIM_TEXT,
    "ok": SUCCESS,
    "bad": ERR,
})

# Import this instead of creating Console() everywhere.
console = Console(theme=EU_THEME, highlight=False)


def rule(title: str = "") -> None:
    """Print a themed horizontal rule."""
    console.rule(f"[muted]{title}[/muted]", style=MUTED)


def label(text: str) -> str:
    """Return Rich markup for a left-side label."""
    return f"[label]{text}[/label]"


def info(msg: str) -> None:
    console.print(f"[dim_text]  >  {msg}[/dim_text]")


def ok(msg: str) -> None:
    console.print(f"[ok]  OK  {msg}[/ok]")


def warn(msg: str) -> None:
    console.print(f"[warn]  !   {msg}[/warn]")


def error(msg: str) -> None:
    console.print(f"[bad]  X   {msg}[/bad]")


def thinking(msg: str = "Processing...") -> None:
    console.print(f"[dim_text]  .   {msg}[/dim_text]")

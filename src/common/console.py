from __future__ import annotations

import os
import sys
from typing import TextIO


_CODES = {
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "dim": "2",
}


def supports_color(no_color: bool = False, stream: TextIO | None = None) -> bool:
    """Return True if we should emit ANSI colors.

    Honors NO_COLOR to disable and FORCE_COLOR to force-enable.
    Defaults to checking isatty() on the given stream (stdout if None).
    """
    if no_color or os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("FORCE_COLOR") in {"1", "true", "TRUE", "yes", "YES"}:
        return True
    s = stream if stream is not None else sys.stdout
    try:
        return bool(getattr(s, "isatty", lambda: False)())
    except Exception:
        return False


def _colorize(enabled: bool, text: str, color: str) -> str:
    if not enabled:
        return text
    code = _CODES.get(color)
    if not code:
        return text
    return f"\x1b[{code}m{text}\x1b[0m"


class Console:
    """Tiny helper for consistent colored prints.

    Usage:
        c = Console(no_color=args.no_color)
        c.info("Hello")
        c.error("Oops")
    """

    def __init__(self, no_color: bool = False, stream: TextIO | None = None) -> None:
        self.stream: TextIO = stream or sys.stdout
        self.enabled: bool = supports_color(no_color=no_color, stream=self.stream)

    # Basic color wrapper
    def color(self, text: str, color: str) -> str:
        return _colorize(self.enabled, text, color)

    # Print helpers
    def _print(self, msg: str, color: str | None = None) -> None:
        s = self.color(msg, color) if color else msg
        print(s, file=self.stream)

    def info(self, msg: str) -> None:
        self._print(msg, "cyan")

    def warn(self, msg: str) -> None:
        self._print(msg, "yellow")

    def error(self, msg: str) -> None:
        self._print(msg, "red")

    def success(self, msg: str) -> None:
        self._print(msg, "green")

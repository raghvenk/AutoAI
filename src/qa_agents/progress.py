from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class ProgressStep:
    percent: int
    label: str


class ConsoleProgress:
    """Small dependency-free progress reporter for CLI and web server logs."""

    def __init__(self, title: str, enabled: bool = True) -> None:
        self.title = title
        self.enabled = enabled
        self._last_percent = -1

    def update(self, percent: int, label: str) -> None:
        if not self.enabled:
            return
        clamped = min(max(percent, 0), 100)
        if clamped < self._last_percent:
            clamped = self._last_percent
        self._last_percent = clamped
        filled = clamped // 5
        bar = "#" * filled + "-" * (20 - filled)
        print(f"[{self.title}] [{bar}] {clamped:3d}% {label}", file=sys.stderr, flush=True)

    def complete(self, label: str = "Done") -> None:
        self.update(100, label)

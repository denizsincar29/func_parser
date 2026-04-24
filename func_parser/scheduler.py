"""Task scheduler for func_parser."""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta
from typing import Callable, List, Optional

from .core.errors import SchedulerError

__all__ = ["ScheduledTask", "Scheduler"]


class ScheduledTask:
    """Represents a scheduled command execution."""

    def __init__(self, spec: str, command: str, callback: Callable) -> None:
        self.spec = spec
        self.command = command
        self.callback = callback
        self._task: Optional[asyncio.Task] = None

    def cancel(self) -> None:
        """Cancel this scheduled task."""
        if self._task:
            self._task.cancel()


class Scheduler:
    """Simple task scheduler supporting ``every Xm/s/h`` and ``at HH:MM`` syntax."""

    INTERVAL_RE = re.compile(
        r'every\s+(\d+(?:\.\d+)?)\s*(s|sec|seconds?|m|min|minutes?|h|hrs?|hours?)',
        re.IGNORECASE,
    )
    AT_RE = re.compile(r'at\s+(\d{1,2}):(\d{2})', re.IGNORECASE)

    def __init__(self, execute_fn: Callable) -> None:
        """*execute_fn* is called with the command string at the scheduled time."""
        self._execute = execute_fn
        self._tasks: List[ScheduledTask] = []

    def parse_spec(self, spec: str) -> float:
        """Parse a schedule spec and return seconds until the next execution.

        Supports:
        - ``every 5m`` / ``every 30s`` / ``every 2h``
        - ``at 12:00``
        """
        m = self.INTERVAL_RE.match(spec.strip())
        if m:
            amount = float(m.group(1))
            unit = m.group(2).lower()
            if unit.startswith("s"):
                return amount
            if unit.startswith("m"):
                return amount * 60
            if unit.startswith("h"):
                return amount * 3600

        m = self.AT_RE.match(spec.strip())
        if m:
            now = datetime.now()
            target = now.replace(
                hour=int(m.group(1)),
                minute=int(m.group(2)),
                second=0,
                microsecond=0,
            )
            if target <= now:
                target += timedelta(days=1)
            return (target - now).total_seconds()

        raise SchedulerError(f"Cannot parse schedule spec: {spec!r}")

    def schedule(self, spec: str, command: str) -> ScheduledTask:
        """Schedule *command* according to *spec*.  Returns a :class:`ScheduledTask`."""
        is_repeating = bool(self.INTERVAL_RE.match(spec.strip()))

        async def _run() -> None:
            if is_repeating:
                while True:
                    delay = self.parse_spec(spec)
                    await asyncio.sleep(delay)
                    await self._execute(command)
            else:
                delay = self.parse_spec(spec)
                await asyncio.sleep(delay)
                await self._execute(command)

        task_obj = ScheduledTask(spec, command, self._execute)
        task_obj._task = asyncio.ensure_future(_run())
        self._tasks.append(task_obj)
        return task_obj

    def cancel_all(self) -> None:
        """Cancel all scheduled tasks."""
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()

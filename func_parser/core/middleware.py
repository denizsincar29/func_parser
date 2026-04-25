"""Middleware chain for func_parser."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, List

from .context import ExecutionContext
from .errors import RateLimitError
from .models import CommandResult

__all__ = ["MiddlewareChain"]


class MiddlewareChain:
    """Manages before/after middleware execution and per-command rate limiting."""

    def __init__(self) -> None:
        self._before: List[Callable] = []
        self._after: List[Callable] = []
        # cmd_name → (max_calls, window_secs, timestamps_list)
        self._rate_limits: Dict[str, list] = {}

    def before(self, fn: Callable) -> Callable:
        """Register a *before-execute* middleware.

        ``fn(ctx, cmd_name, args) -> None | dict``
        """
        self._before.append(fn)
        return fn

    def after(self, fn: Callable) -> Callable:
        """Register an *after-execute* middleware.

        ``fn(ctx, result) -> None | CommandResult``
        """
        self._after.append(fn)
        return fn

    def set_rate_limit(self, cmd_name: str, max_calls: int, window_secs: float = 1.0) -> None:
        """Configure a sliding-window rate limit for *cmd_name*."""
        self._rate_limits[cmd_name] = [max_calls, window_secs, []]

    def check_rate_limit(self, cmd_name: str) -> None:
        """Raise :class:`RateLimitError` if the rate limit for *cmd_name* is exceeded."""
        if cmd_name not in self._rate_limits:
            return
        max_calls, window, timestamps = self._rate_limits[cmd_name]
        now = time.monotonic()
        fresh = [t for t in timestamps if now - t < window]
        self._rate_limits[cmd_name][2] = fresh
        if len(fresh) >= max_calls:
            raise RateLimitError(cmd_name)
        self._rate_limits[cmd_name][2].append(now)

    async def run_before(
        self, ctx: ExecutionContext, cmd_name: str, args: dict
    ) -> dict:
        """Run all before-middleware in registration order."""
        for fn in self._before:
            result = fn(ctx, cmd_name, args)
            if asyncio.iscoroutine(result):
                result = await result
            if isinstance(result, dict):
                args = result
        return args

    async def run_after(
        self, ctx: ExecutionContext, result: CommandResult
    ) -> CommandResult:
        """Run all after-middleware in registration order."""
        for fn in self._after:
            r = fn(ctx, result)
            if asyncio.iscoroutine(r):
                r = await r
            if isinstance(r, CommandResult):
                result = r
        return result

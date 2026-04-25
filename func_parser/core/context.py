"""Execution context passed to every command handler."""
from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

__all__ = ["User", "OutputBuffer", "ExecutionContext"]


@dataclass
class User:
    """Represents the entity executing commands."""
    id: str = "anonymous"
    name: str = "anonymous"
    roles: List[str] = field(default_factory=lambda: ["user"])

    def has_role(self, role: str) -> bool:
        """Return True if user has *role* or is an admin."""
        return role in self.roles or "admin" in self.roles


class OutputBuffer:
    """Collects output lines and supports async streaming."""

    def __init__(self) -> None:
        self._lines: List[str] = []
        self._queue: asyncio.Queue = asyncio.Queue()

    def write(self, text: str) -> None:
        """Append *text* to the buffer and enqueue for streaming."""
        self._lines.append(text)
        try:
            self._queue.put_nowait(text)
        except asyncio.QueueFull:
            pass

    def getvalue(self) -> str:
        """Return all buffered lines joined by newlines."""
        return "\n".join(self._lines)

    async def stream(self) -> AsyncIterator[str]:
        """Async generator that yields output lines as they arrive."""
        while True:
            yield await self._queue.get()


class ExecutionContext:
    """Context passed to every command handler."""

    def __init__(
        self,
        user: Optional[User] = None,
        vars: Optional[Dict[str, Any]] = None,
        env: Optional[Dict[str, str]] = None,
        permissions: Optional[List[str]] = None,
        dry_run: bool = False,
        debug: bool = False,
    ) -> None:
        self.user: User = user or User()
        self.vars: Dict[str, Any] = vars or {}
        self.env: Dict[str, str] = env or dict(os.environ)
        self.permissions: List[str] = permissions or []
        self.dry_run: bool = dry_run
        self.debug: bool = debug
        self.output: OutputBuffer = OutputBuffer()
        self._history: List[Any] = []
        self._redo_stack: List[Any] = []
        self._metadata: Dict[str, Any] = {}

    def set_var(self, name: str, value: Any) -> None:
        """Set a context variable."""
        self.vars[name] = value

    def get_var(self, name: str, default: Any = None) -> Any:
        """Look up a variable (local vars, then environment)."""
        return self.vars.get(name, self.env.get(name, default))

    def expand_vars(self, text: str) -> str:
        """Expand ``${var}`` and ``$VAR`` placeholders in *text*."""
        def replace(m: re.Match) -> str:
            key = m.group(1) or m.group(2)
            return str(self.get_var(key, m.group(0)))

        text = re.sub(r'\$\{([^}]+)\}', replace, text)
        text = re.sub(r'\$([A-Z_][A-Z0-9_]*)', replace, text)
        return text

    def push_history(self, entry: Any) -> None:
        """Push an entry onto the undo history."""
        self._history.append(entry)
        self._redo_stack.clear()

    def undo(self) -> Any:
        """Pop the last history entry (for undo)."""
        if self._history:
            entry = self._history.pop()
            self._redo_stack.append(entry)
            return entry
        return None

    def redo(self) -> Any:
        """Re-apply the last undone entry."""
        if self._redo_stack:
            entry = self._redo_stack.pop()
            self._history.append(entry)
            return entry
        return None

    @property
    def metadata(self) -> Dict[str, Any]:
        """Arbitrary metadata dict for use by middleware/plugins."""
        return self._metadata

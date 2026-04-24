"""Command registry for func_parser."""
from __future__ import annotations

from typing import Callable, Dict, Iterator, List, Optional

from .models import CommandInfo

__all__ = ["CommandRegistry", "NamespaceView"]


class NamespaceView:
    """A filtered view of a :class:`CommandRegistry` for a given namespace prefix."""

    def __init__(self, registry: "CommandRegistry", namespace: str) -> None:
        self._registry = registry
        self._ns = namespace

    def get(self, name: str) -> Optional[CommandInfo]:
        """Look up *name* within this namespace."""
        return self._registry.get(f"{self._ns}.{name}")

    def all_commands(self) -> List[CommandInfo]:
        """All commands belonging to this namespace."""
        prefix = f"{self._ns}."
        seen: set[str] = set()
        result: List[CommandInfo] = []
        for cmd in self._registry.all_commands():
            if cmd.name.startswith(prefix) and cmd.name not in seen:
                seen.add(cmd.name)
                result.append(cmd)
        return result


class CommandRegistry:
    """Registry that maps command names (and aliases) to :class:`CommandInfo` objects."""

    def __init__(self) -> None:
        self._commands: Dict[str, CommandInfo] = {}   # canonical name → info
        self._aliases: Dict[str, str] = {}            # alias → canonical name
        self._default_handler: Optional[Callable] = None

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, cmd_info: CommandInfo) -> None:
        """Register *cmd_info*, including all its aliases."""
        self._commands[cmd_info.name] = cmd_info
        for alias in cmd_info.aliases:
            self._aliases[alias] = cmd_info.name

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, name: str) -> Optional[CommandInfo]:
        """Return the :class:`CommandInfo` for *name* (or its alias), or *None*."""
        if name in self._commands:
            return self._commands[name]
        canonical = self._aliases.get(name)
        if canonical:
            return self._commands.get(canonical)
        return None

    def all_commands(self) -> List[CommandInfo]:
        """Return a de-duplicated list of all registered commands."""
        return list(self._commands.values())

    def set_default(self, handler: Callable) -> None:
        """Set the handler invoked for non-command (plain-text) input."""
        self._default_handler = handler

    @property
    def default_handler(self) -> Optional[Callable]:
        """The registered default text handler, or *None*."""
        return self._default_handler

    def namespace(self, ns: str) -> NamespaceView:
        """Return a :class:`NamespaceView` filtered to *ns*."""
        return NamespaceView(self, ns)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def __contains__(self, name: str) -> bool:
        return name in self._commands or name in self._aliases

    def __iter__(self) -> Iterator[CommandInfo]:
        return iter(self._commands.values())

    def __len__(self) -> int:
        return len(self._commands)

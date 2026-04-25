"""I/O abstraction layer for func_parser."""
from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Optional

__all__ = [
    "InputProvider", "OutputHandler", "CompletionProvider",
    "StdinInputProvider", "StdoutOutputHandler", "FileOutputHandler",
    "ClipboardOutputHandler", "SimpleCompletionProvider",
]


class InputProvider(ABC):
    """Abstract base class for input sources."""

    @abstractmethod
    async def read(self, prompt: str = "") -> str:
        """Read a line of input."""
        ...


class OutputHandler(ABC):
    """Abstract base class for output destinations."""

    @abstractmethod
    async def write(self, text: str) -> None:
        """Write *text* to the output destination."""
        ...

    async def writeln(self, text: str) -> None:
        """Write *text* followed by a newline."""
        await self.write(text + "\n")


class CompletionProvider(ABC):
    """Abstract base class for auto-completion providers."""

    @abstractmethod
    def get_completions(self, document: str, command_names: List[str]) -> List[str]:
        """Return completion suggestions for *document*."""
        ...


class StdinInputProvider(InputProvider):
    """Reads from stdin (supports both TTY and piped input)."""

    async def read(self, prompt: str = "") -> str:
        if sys.stdin.isatty():
            return input(prompt)
        line = sys.stdin.readline()
        if not line:
            raise EOFError
        return line.rstrip("\n")


class StdoutOutputHandler(OutputHandler):
    """Writes to stdout."""

    async def write(self, text: str) -> None:
        print(text, end="")


class FileOutputHandler(OutputHandler):
    """Writes to a file."""

    def __init__(self, path: str, append: bool = False) -> None:
        self.path = path
        self.append = append

    async def write(self, text: str) -> None:
        mode = "a" if self.append else "w"
        with open(self.path, mode, encoding="utf-8") as fh:
            fh.write(text)


class ClipboardOutputHandler(OutputHandler):
    """Copies output to the system clipboard via *pyperclip*."""

    async def write(self, text: str) -> None:
        try:
            import pyperclip  # type: ignore
            pyperclip.copy(text)
        except ImportError as exc:
            raise ImportError(
                "pyperclip is required for clipboard support. "
                "Install with: pip install pyperclip"
            ) from exc


class SimpleCompletionProvider(CompletionProvider):
    """Basic prefix-based completion for command names."""

    def get_completions(self, document: str, command_names: List[str]) -> List[str]:
        word = document.lstrip("/")
        return [f"/{n}" for n in command_names if n.startswith(word)]

"""CLI adapter for func_parser using prompt_toolkit."""
from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..decorators import CommandParser
    from ..core.context import ExecutionContext

__all__ = ["CLIAdapter"]

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.lexers import Lexer
    from prompt_toolkit.document import Document
    from prompt_toolkit.formatted_text import FormattedText
    from prompt_toolkit.validation import Validator, ValidationError as PTValidationError
    from prompt_toolkit.history import InMemoryHistory
    _PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    _PROMPT_TOOLKIT_AVAILABLE = False


class _FallbackCompleter:
    """Dummy completer used when prompt_toolkit is not installed."""
    pass


class _FallbackLexer:
    """Dummy lexer used when prompt_toolkit is not installed."""
    pass


if _PROMPT_TOOLKIT_AVAILABLE:
    class CommandCompleter(Completer):
        """Provides tab-completion for command names and arguments."""

        def __init__(self, parser: "CommandParser") -> None:
            self._parser = parser

        def get_completions(self, document: Document, complete_event):
            text = document.text_before_cursor
            word = document.get_word_before_cursor(WORD=True)
            names = [cmd.name for cmd in self._parser.registry.all_commands()]
            if text.lstrip().startswith("/") or not text.strip():
                for name in names:
                    display = f"/{name}"
                    if display.startswith(text.lstrip()) or name.startswith(word.lstrip("/")):
                        yield Completion(
                            f"/{name}",
                            start_position=-len(text.lstrip()),
                            display=display,
                        )

    class CommandLexer(Lexer):
        """Syntax-highlights command input."""

        def __init__(self, parser: "CommandParser") -> None:
            self._parser = parser

        def lex_document(self, document: Document):
            names = {cmd.name for cmd in self._parser.registry.all_commands()}

            def get_line(lineno: int):
                line = document.lines[lineno]
                tokens: List[tuple] = []
                if line.startswith("/"):
                    parts = line.split(None, 1)
                    cmd = parts[0].lstrip("/")
                    if cmd in names:
                        tokens.append(("class:command", parts[0]))
                        if len(parts) > 1:
                            tokens.append(("class:arg", " " + parts[1]))
                    else:
                        tokens.append(("class:error", line))
                else:
                    tokens.append(("class:text", line))
                return tokens

            return get_line

    class _LiveValidator(Validator):
        """Validates input before submission."""

        def __init__(self, parser: "CommandParser") -> None:
            self._parser = parser

        def validate(self, document: Document) -> None:
            text = document.text.strip()
            if not text or text.startswith("#"):
                return
            # Basic validation: check command exists
            if text.startswith("/") and not text.startswith("//"):
                cmd_name = text.lstrip("/").split()[0] if text.lstrip("/").split() else ""
                if cmd_name and cmd_name not in ("help", "execute") and self._parser.registry.get(cmd_name) is None:
                    raise PTValidationError(
                        message=f"Unknown command: /{cmd_name}",
                        cursor_position=len(text),
                    )


class CLIAdapter:
    """CLI adapter that wraps a :class:`CommandParser` with prompt_toolkit UI."""

    def __init__(
        self,
        parser: "CommandParser",
        prompt: str = "> ",
        ctx: Optional["ExecutionContext"] = None,
    ) -> None:
        self._parser = parser
        self._prompt = prompt
        self._ctx = ctx
        self._session = None
        if _PROMPT_TOOLKIT_AVAILABLE:
            self._session = PromptSession(
                history=InMemoryHistory(),
                completer=CommandCompleter(parser),
                lexer=CommandLexer(parser),
                validator=_LiveValidator(parser),
                validate_while_typing=False,
            )

    async def run(self) -> None:
        """Start the async interactive CLI loop."""
        from ..core.context import ExecutionContext
        ctx = self._ctx or ExecutionContext()

        if not _PROMPT_TOOLKIT_AVAILABLE:
            print("prompt_toolkit not installed. Falling back to basic input.")
            await self._basic_loop(ctx)
            return

        while True:
            try:
                text = await self._session.prompt_async(self._prompt)
            except (EOFError, KeyboardInterrupt):
                print("\nBye!")
                break

            text = text.strip()
            if not text:
                continue

            # Handle multiline continuation (trailing backslash)
            while text.endswith("\\"):
                text = text[:-1]
                try:
                    continuation = await self._session.prompt_async("... ")
                    text += "\n" + continuation.strip()
                except (EOFError, KeyboardInterrupt):
                    break

            result = await self._parser.execute(text, ctx)
            if result.output is not None:
                print(result.output)
            if result.error is not None and result.status != "success":
                print(f"Error: {result.error}")

    async def _basic_loop(self, ctx: "ExecutionContext") -> None:
        """Fallback loop without prompt_toolkit."""
        import sys
        while True:
            try:
                if sys.stdin.isatty():
                    line = input(self._prompt)
                else:
                    line = sys.stdin.readline()
                    if not line:
                        break
                    line = line.rstrip("\n")
            except (EOFError, KeyboardInterrupt):
                break
            line = line.strip()
            if not line:
                continue
            result = await self._parser.execute(line, ctx)
            if result.output is not None:
                print(result.output)
            if result.error is not None and result.status != "success":
                print(f"Error: {result.error}")

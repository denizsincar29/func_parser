"""Data models for func_parser."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, List, Dict, Type
import enum

__all__ = ["ArgKind", "ArgDef", "CommandInfo", "CommandResult", "OutputRedirect"]


class ArgKind(enum.Enum):
    """Enumeration of argument kinds."""
    POSITIONAL = "positional"
    KEYWORD = "keyword"
    VARIADIC = "variadic"


@dataclass
class ArgDef:
    """Definition of a single command argument."""
    name: str
    type: Type = str
    required: bool = True
    default: Any = None
    help: str = ""
    variadic: bool = False      # *args style - collects remaining positional args
    choices: Optional[List] = None
    min: Optional[float] = None  # for numeric ranges
    max: Optional[float] = None
    regex: Optional[str] = None
    preset: Optional[str] = None  # "email", "url", "phone"
    secret: bool = False          # password-style
    validators: List[Callable] = field(default_factory=list)
    kind: ArgKind = ArgKind.POSITIONAL

    def __post_init__(self):
        if self.default is not None:
            self.required = False
        if self.variadic:
            self.kind = ArgKind.VARIADIC


@dataclass
class CommandInfo:
    """Metadata describing a registered command."""
    name: str
    handler: Optional[Callable] = None
    args: List[ArgDef] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    middleware_before: List[Callable] = field(default_factory=list)
    middleware_after: List[Callable] = field(default_factory=list)
    validators: List[Callable] = field(default_factory=list)
    help: str = ""
    is_event: bool = False
    rate_limit: Optional[float] = None  # max calls per second
    hidden: bool = False


@dataclass
class CommandResult:
    """Result of executing a command."""
    name: str
    args: Dict[str, Any]
    status: str  # "success", "error", "unknown", "permission_denied", "missing_args", "invalid_args"
    output: Any = None
    error: Optional[Exception] = None
    is_event: bool = False
    redirect: Optional["OutputRedirect"] = None

    @property
    def ok(self) -> bool:
        """True if the command succeeded."""
        return self.status == "success"

    def __repr__(self) -> str:
        return f"CommandResult(name={self.name!r}, status={self.status!r}, output={self.output!r})"


@dataclass
class OutputRedirect:
    """Describes where command output should be redirected."""
    target: str   # file path, "clipboard", or "stdout"
    append: bool = False

    @property
    def is_clipboard(self) -> bool:
        """True if output should go to clipboard."""
        return self.target == "clipboard"

    @property
    def is_file(self) -> bool:
        """True if output should go to a file."""
        return self.target not in ("clipboard", "stdout")

"""AST node definitions for the func_parser command language."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from ..core.models import OutputRedirect

__all__ = [
    "ASTNode",
    "CommandNode",
    "PipelineNode",
    "AndNode",
    "OrNode",
    "SetVarNode",
    "ExecuteScriptNode",
    "TextNode",
    "IfNode",
]


class ASTNode:
    """Abstract base class for all AST nodes."""
    pass


@dataclass
class CommandNode(ASTNode):
    """A single command invocation."""
    name: str
    args: List[str] = field(default_factory=list)
    kwargs: Dict[str, str] = field(default_factory=dict)
    redirect: Optional[OutputRedirect] = None


@dataclass
class PipelineNode(ASTNode):
    """A chain of commands connected by ``|``."""
    commands: List[CommandNode] = field(default_factory=list)


@dataclass
class AndNode(ASTNode):
    """Execute *right* only if *left* succeeds (``&&``)."""
    left: ASTNode = field(default_factory=lambda: TextNode(""))
    right: ASTNode = field(default_factory=lambda: TextNode(""))


@dataclass
class OrNode(ASTNode):
    """Execute *right* only if *left* fails (``||``)."""
    left: ASTNode = field(default_factory=lambda: TextNode(""))
    right: ASTNode = field(default_factory=lambda: TextNode(""))


@dataclass
class SetVarNode(ASTNode):
    """``//set name=value`` or ``//setenv name=value``."""
    name: str = ""
    value: str = ""
    scope: str = "local"  # "local" | "env"


@dataclass
class ExecuteScriptNode(ASTNode):
    """``/execute script.txt`` — execute a script file."""
    path: str = ""


@dataclass
class TextNode(ASTNode):
    """Plain text input (goes to the default handler)."""
    content: str = ""


@dataclass
class IfNode(ASTNode):
    """Basic conditional node (optional/future use)."""
    condition: str = ""
    body: Optional[ASTNode] = None
    else_body: Optional[ASTNode] = None

"""Tests for the parser (AST building)."""
import pytest
import asyncio
from func_parser import CommandParser
from func_parser.parser.ast_nodes import (
    CommandNode, PipelineNode, AndNode, OrNode, SetVarNode,
    TextNode, IfNode, WhileNode,
)
from func_parser.parser.executor import Parser
from func_parser.core.registry import CommandRegistry
from func_parser.core.variables import VariableStore
from func_parser.core.permissions import PermissionChecker
from func_parser.core.middleware import MiddlewareChain
from func_parser.core.pipeline import AsyncPipeline
from func_parser.core.context import ExecutionContext


def make_parser(**kwargs):
    registry = CommandRegistry()
    var_store = VariableStore()
    return Parser(
        registry=registry,
        var_store=var_store,
        permission_checker=PermissionChecker(),
        middleware_chain=MiddlewareChain(),
        pipeline=AsyncPipeline(),
        **kwargs,
    ), registry, var_store


class TestParseAST:
    def test_command_node(self):
        p, *_ = make_parser()
        node = p.parse("/greet Alice")
        assert isinstance(node, CommandNode)
        assert node.name == "greet"
        assert node.args == ["Alice"]

    def test_kwarg_parsing(self):
        p, *_ = make_parser()
        node = p.parse("/create name=Alice age=30")
        assert isinstance(node, CommandNode)
        assert node.kwargs == {"name": "Alice", "age": "30"}

    def test_plain_text_is_text_node(self):
        p, *_ = make_parser()
        node = p.parse("hello world")
        assert isinstance(node, TextNode)

    def test_pipeline(self):
        p, registry, _ = make_parser()
        node = p.parse("/a | /b")
        assert isinstance(node, PipelineNode)
        assert len(node.commands) == 2

    def test_and_node(self):
        p, *_ = make_parser()
        node = p.parse("/a && /b")
        assert isinstance(node, AndNode)

    def test_or_node(self):
        p, *_ = make_parser()
        node = p.parse("/a || /b")
        assert isinstance(node, OrNode)

    def test_set_var_node(self):
        p, *_ = make_parser()
        node = p.parse("//set x=5")
        assert isinstance(node, SetVarNode)
        assert node.name == "x"
        assert node.value == "5"
        assert node.scope == "local"

    def test_setenv_node(self):
        p, *_ = make_parser()
        node = p.parse("//setenv FOO=bar")
        assert isinstance(node, SetVarNode)
        assert node.scope == "env"

    def test_redirect_out(self):
        p, *_ = make_parser()
        node = p.parse("/cmd > out.txt")
        assert isinstance(node, CommandNode)
        assert node.redirect is not None
        assert node.redirect.target == "out.txt"
        assert not node.redirect.append

    def test_redirect_append(self):
        p, *_ = make_parser()
        node = p.parse("/cmd >> out.txt")
        assert isinstance(node, CommandNode)
        assert node.redirect.append is True

    def test_redirect_clipboard(self):
        p, *_ = make_parser()
        node = p.parse("/cmd >clipboard")
        assert isinstance(node, CommandNode)
        assert node.redirect.is_clipboard

    def test_variable_substitution(self):
        p, _, var_store = make_parser()
        var_store.set("name", "Alice")
        node = p.parse("/greet ${name}")
        assert isinstance(node, CommandNode)
        assert node.args == ["Alice"]

"""Tests for command execution (decorator API)."""
import asyncio
import pytest
import pytest_asyncio
from func_parser import CommandParser, ExecutionContext, User
from func_parser.core.errors import (
    CommandNotFoundError, MissingArgError, InvalidArgError,
    PermissionDeniedError, RateLimitError,
)


pytestmark = pytest.mark.asyncio


@pytest.fixture
def parser():
    return CommandParser()


@pytest.fixture
def ctx():
    return ExecutionContext(user=User(id="u1", roles=["admin"]))


@pytest.fixture
def user_ctx():
    return ExecutionContext(user=User(id="u2", roles=["user"]))


# ---------------------------------------------------------------------------
# Basic command execution
# ---------------------------------------------------------------------------

async def test_simple_command(parser, ctx):
    @parser.command("greet")
    async def greet(ctx, name: str):
        return f"Hello, {name}!"

    result = await parser.execute("/greet Alice", ctx)
    assert result.ok
    assert result.output == "Hello, Alice!"


async def test_sync_handler(parser, ctx):
    @parser.command("add")
    def add(ctx, a: int, b: int):
        return a + b

    result = await parser.execute("/add 3 4", ctx)
    assert result.ok
    assert result.output == 7


async def test_default_text_handler(parser, ctx):
    @parser.default_command
    async def on_text(ctx, content: str):
        return f"echo: {content}"

    result = await parser.execute("hello world", ctx)
    assert result.ok
    assert result.output == "echo: hello world"


async def test_unknown_command_returns_unknown(parser, ctx):
    result = await parser.execute("/nonexistent", ctx)
    assert result.status == "unknown"
    assert isinstance(result.error, CommandNotFoundError)


# ---------------------------------------------------------------------------
# Argument handling
# ---------------------------------------------------------------------------

async def test_missing_required_arg(parser, ctx):
    @parser.command("req")
    async def req(ctx, name: str):
        return name

    result = await parser.execute("/req", ctx)
    assert result.status == "missing_args"


async def test_optional_arg_default(parser, ctx):
    from func_parser import arg

    @parser.command("greet2")
    @arg("name", type=str, required=False, default="World")
    async def greet2(ctx, name: str):
        return f"Hello, {name}!"

    result = await parser.execute("/greet2", ctx)
    assert result.ok
    assert result.output == "Hello, World!"


async def test_type_coercion(parser, ctx):
    @parser.command("double")
    async def double(ctx, n: int):
        return n * 2

    result = await parser.execute("/double 21", ctx)
    assert result.ok
    assert result.output == 42


async def test_invalid_type_coercion(parser, ctx):
    @parser.command("typefail")
    async def typefail(ctx, n: int):
        return n

    result = await parser.execute("/typefail notanint", ctx)
    assert result.status == "invalid_args"


async def test_variadic_args(parser, ctx):
    from func_parser import arg

    @parser.command("sum")
    @arg("nums", type=int, variadic=True)
    async def sum_cmd(ctx, nums):
        return sum(nums)

    result = await parser.execute("/sum 1 2 3 4", ctx)
    assert result.ok
    assert result.output == 10


async def test_kwarg(parser, ctx):
    @parser.command("greet3")
    async def greet3(ctx, name: str):
        return name

    result = await parser.execute("/greet3 name=Bob", ctx)
    assert result.ok
    assert result.output == "Bob"


# ---------------------------------------------------------------------------
# Aliases
# ---------------------------------------------------------------------------

async def test_alias(parser, ctx):
    @parser.command("verbose_cmd", aliases=["vc"])
    async def vc(ctx):
        return "verbose"

    result = await parser.execute("/vc", ctx)
    assert result.ok
    assert result.output == "verbose"


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

async def test_permission_denied(parser, ctx, user_ctx):
    from func_parser import permission as perm_decorator

    @parser.command("admin_only")
    @perm_decorator("admin")
    async def admin_only(ctx):
        return "secret"

    # admin can run it
    result_admin = await parser.execute("/admin_only", ctx)
    assert result_admin.ok

    # non-admin gets denied
    result_user = await parser.execute("/admin_only", user_ctx)
    assert result_user.status == "permission_denied"


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------

async def test_dry_run():
    p = CommandParser(dry_run=True)

    @p.command("action")
    async def action(ctx):
        raise RuntimeError("Should not run in dry_run mode")

    ctx = ExecutionContext(dry_run=True)
    result = await p.execute("/action", ctx)
    assert result.status == "dry_run"


# ---------------------------------------------------------------------------
# Variable system
# ---------------------------------------------------------------------------

async def test_set_var(parser, ctx):
    result = await parser.execute("//set greeting=hello", ctx)
    assert result.ok
    assert result.args["name"] == "greeting"
    assert result.args["value"] == "hello"


async def test_var_expansion(parser, ctx):
    @parser.command("echo")
    async def echo(ctx, msg: str):
        return msg

    await parser.execute("//set msg=world", ctx)
    result = await parser.execute("/echo ${msg}", ctx)
    assert result.ok
    assert result.output == "world"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

async def test_pipeline(parser, ctx):
    @parser.command("upper")
    async def upper(ctx, text: str):
        return text.upper()

    @parser.command("exclaim")
    async def exclaim(ctx, text: str):
        return text + "!"

    result = await parser.execute("/upper hello | /exclaim", ctx)
    assert result.ok
    assert result.output == "HELLO!"


# ---------------------------------------------------------------------------
# && and || operators
# ---------------------------------------------------------------------------

async def test_and_both_run(parser, ctx):
    calls = []

    @parser.command("a")
    async def a(ctx):
        calls.append("a")
        return "a"

    @parser.command("b")
    async def b(ctx):
        calls.append("b")
        return "b"

    result = await parser.execute("/a && /b", ctx)
    assert "a" in calls and "b" in calls
    assert result.output == "b"


async def test_and_short_circuit(parser, ctx):
    calls = []

    @parser.command("fail_cmd")
    async def fail_cmd(ctx):
        raise RuntimeError("failed")

    @parser.command("after")
    async def after(ctx):
        calls.append("after")
        return "after"

    result = await parser.execute("/fail_cmd && /after", ctx)
    assert "after" not in calls


async def test_or_second_runs_on_failure(parser, ctx):
    @parser.command("fail2")
    async def fail2(ctx):
        raise RuntimeError("fail")

    @parser.command("fallback")
    async def fallback(ctx):
        return "fallback"

    result = await parser.execute("/fail2 || /fallback", ctx)
    assert result.ok
    assert result.output == "fallback"


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

async def test_global_before_middleware(parser, ctx):
    log = []

    @parser._middleware.before
    def before_mw(ctx, cmd_name, args):
        log.append(f"before:{cmd_name}")
        return args

    @parser.command("mw_test")
    async def mw_test(ctx):
        return "ok"

    await parser.execute("/mw_test", ctx)
    assert "before:mw_test" in log


async def test_rate_limit(parser, ctx):
    parser._middleware.set_rate_limit("limited", max_calls=2, window_secs=10.0)

    @parser.command("limited")
    async def limited(ctx):
        return "ok"

    await parser.execute("/limited", ctx)
    await parser.execute("/limited", ctx)
    result = await parser.execute("/limited", ctx)
    assert result.status == "error"
    assert isinstance(result.error, RateLimitError)


# ---------------------------------------------------------------------------
# WhileNode execution
# ---------------------------------------------------------------------------

async def test_while_node_executes():
    from func_parser.parser.ast_nodes import WhileNode, CommandNode, SetVarNode
    from func_parser.parser.executor import Parser
    from func_parser.core.registry import CommandRegistry
    from func_parser.core.variables import VariableStore
    from func_parser.core.permissions import PermissionChecker
    from func_parser.core.middleware import MiddlewareChain
    from func_parser.core.pipeline import AsyncPipeline

    registry = CommandRegistry()
    var_store = VariableStore()
    var_store.set("running", "true")

    counter = [0]

    from func_parser.core.models import CommandInfo
    from func_parser.core.models import ArgDef

    async def tick_handler(ctx):
        counter[0] += 1
        if counter[0] >= 3:
            var_store.set("running", "false")
        return counter[0]

    from func_parser.core.models import CommandInfo
    cmd_info = CommandInfo(name="tick", handler=tick_handler)
    registry.register(cmd_info)

    p = Parser(
        registry=registry,
        var_store=var_store,
        permission_checker=PermissionChecker(),
        middleware_chain=MiddlewareChain(),
        pipeline=AsyncPipeline(),
    )
    ctx = ExecutionContext()

    while_node = WhileNode(
        condition="running",
        body=CommandNode(name="tick"),
        max_iterations=100,
    )
    result = await p.execute_node(while_node, ctx)
    assert counter[0] == 3


async def test_while_max_iterations():
    from func_parser.parser.ast_nodes import WhileNode, CommandNode
    from func_parser.parser.executor import Parser
    from func_parser.core.registry import CommandRegistry
    from func_parser.core.variables import VariableStore
    from func_parser.core.permissions import PermissionChecker
    from func_parser.core.middleware import MiddlewareChain
    from func_parser.core.pipeline import AsyncPipeline
    from func_parser.core.models import CommandInfo

    registry = CommandRegistry()
    var_store = VariableStore()
    var_store.set("always", "true")

    calls = [0]

    async def noop(ctx):
        calls[0] += 1
        return "ok"

    cmd_info = CommandInfo(name="noop", handler=noop)
    registry.register(cmd_info)

    p = Parser(
        registry=registry,
        var_store=var_store,
        permission_checker=PermissionChecker(),
        middleware_chain=MiddlewareChain(),
        pipeline=AsyncPipeline(),
    )
    ctx = ExecutionContext()
    while_node = WhileNode(
        condition="always",
        body=CommandNode(name="noop"),
        max_iterations=5,
    )
    await p.execute_node(while_node, ctx)
    assert calls[0] == 5

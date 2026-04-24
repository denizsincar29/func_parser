"""Decorator API for registering commands in func_parser."""
from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable, List, Optional, TYPE_CHECKING

from .core.errors import FuncParserError
from .core.middleware import MiddlewareChain
from .core.models import ArgDef, CommandInfo
from .core.permissions import PermissionChecker
from .core.pipeline import AsyncPipeline
from .core.registry import CommandRegistry
from .core.variables import VariableStore

if TYPE_CHECKING:
    from .core.context import ExecutionContext
    from .core.models import CommandResult

__all__ = [
    "command", "arg", "validator", "permission", "middleware", "default_command",
    "CommandParser",
    "get_default_registry", "get_default_parser",
    "_DEFAULT_REGISTRY",
]

_DEFAULT_REGISTRY: CommandRegistry = CommandRegistry()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_or_create_cmd(registry: CommandRegistry, name: str) -> CommandInfo:
    """Return existing CommandInfo or create a new one."""
    existing = registry.get(name)
    if existing is not None and existing.name == name:
        return existing
    return CommandInfo(name=name)


def _collect_pending(fn: Callable, cmd: CommandInfo) -> None:
    """Flush any pending @arg / @permission / @middleware / @validator onto *cmd*."""
    if hasattr(fn, "_pending_args"):
        if not cmd.args:
            cmd.args = list(fn._pending_args)
        del fn._pending_args

    if hasattr(fn, "_pending_validators"):
        cmd.validators.extend(fn._pending_validators)
        del fn._pending_validators

    if hasattr(fn, "_pending_permissions"):
        cmd.permissions.extend(fn._pending_permissions)
        del fn._pending_permissions

    if hasattr(fn, "_pending_middleware_before"):
        cmd.middleware_before.extend(fn._pending_middleware_before)
        del fn._pending_middleware_before

    if hasattr(fn, "_pending_middleware_after"):
        cmd.middleware_after.extend(fn._pending_middleware_after)
        del fn._pending_middleware_after


def _infer_args_from_hints(cmd: CommandInfo, fn: Callable) -> None:
    """Infer ArgDef list from *fn*'s signature if no @arg decorators were used."""
    if cmd.args:
        return
    sig = inspect.signature(fn)
    for pname, param in sig.parameters.items():
        if pname == "ctx":
            continue
        ann = param.annotation if param.annotation != inspect.Parameter.empty else str
        default = param.default if param.default != inspect.Parameter.empty else None
        required = param.default == inspect.Parameter.empty
        cmd.args.append(ArgDef(
            name=pname,
            type=ann,
            required=required,
            default=default,
            help=f"Argument: {pname}",
        ))


# ---------------------------------------------------------------------------
# Global decorators (use the global _DEFAULT_REGISTRY)
# ---------------------------------------------------------------------------

def command(
    name: str,
    *,
    aliases: Optional[List[str]] = None,
    help: str = "",
    is_event: bool = False,
    hidden: bool = False,
    rate_limit: Optional[float] = None,
) -> Callable:
    """Register a function as a command in the global registry."""
    def decorator(fn: Callable) -> Callable:
        cmd = _get_or_create_cmd(_DEFAULT_REGISTRY, name)
        cmd.handler = fn
        cmd.aliases = aliases or []
        cmd.help = help or fn.__doc__ or ""
        cmd.is_event = is_event
        cmd.hidden = hidden
        if rate_limit is not None:
            cmd.rate_limit = rate_limit
        _collect_pending(fn, cmd)
        _infer_args_from_hints(cmd, fn)
        _DEFAULT_REGISTRY.register(cmd)
        fn._cmd_info = cmd  # type: ignore[attr-defined]
        return fn
    return decorator


def arg(
    name: str,
    *,
    type: type = str,
    required: bool = True,
    default: Any = None,
    help: str = "",
    variadic: bool = False,
    choices: Optional[List] = None,
    min: Optional[float] = None,
    max: Optional[float] = None,
    regex: Optional[str] = None,
    preset: Optional[str] = None,
    secret: bool = False,
) -> Callable:
    """Stage an argument definition on the decorated function."""
    def decorator(fn: Callable) -> Callable:
        if not hasattr(fn, "_pending_args"):
            fn._pending_args = []  # type: ignore[attr-defined]
        fn._pending_args.insert(0, ArgDef(  # type: ignore[attr-defined]
            name=name, type=type, required=required, default=default,
            help=help, variadic=variadic, choices=choices,
            min=min, max=max, regex=regex, preset=preset, secret=secret,
        ))
        return fn
    return decorator


def validator(fn_validator: Callable) -> Callable:
    """Stage a custom validator on the decorated function."""
    def decorator(fn: Callable) -> Callable:
        if not hasattr(fn, "_pending_validators"):
            fn._pending_validators = []  # type: ignore[attr-defined]
        fn._pending_validators.append(fn_validator)  # type: ignore[attr-defined]
        return fn
    return decorator


def permission(*perms: str) -> Callable:
    """Stage required permissions on the decorated function."""
    def decorator(fn: Callable) -> Callable:
        if not hasattr(fn, "_pending_permissions"):
            fn._pending_permissions = []  # type: ignore[attr-defined]
        fn._pending_permissions.extend(perms)  # type: ignore[attr-defined]
        return fn
    return decorator


def middleware(*, before: Optional[Callable] = None, after: Optional[Callable] = None) -> Callable:
    """Stage command-level middleware on the decorated function."""
    def decorator(fn: Callable) -> Callable:
        if before:
            if not hasattr(fn, "_pending_middleware_before"):
                fn._pending_middleware_before = []  # type: ignore[attr-defined]
            fn._pending_middleware_before.append(before)  # type: ignore[attr-defined]
        if after:
            if not hasattr(fn, "_pending_middleware_after"):
                fn._pending_middleware_after = []  # type: ignore[attr-defined]
            fn._pending_middleware_after.append(after)  # type: ignore[attr-defined]
        return fn
    return decorator


def default_command(fn: Callable) -> Callable:
    """Register *fn* as the global default text handler."""
    _DEFAULT_REGISTRY.set_default(fn)
    return fn


def get_default_registry() -> CommandRegistry:
    """Return the global default :class:`CommandRegistry`."""
    return _DEFAULT_REGISTRY


def get_default_parser() -> "CommandParser":
    """Return a :class:`CommandParser` backed by the global registry."""
    p = CommandParser()
    p.registry = _DEFAULT_REGISTRY
    return p


# ---------------------------------------------------------------------------
# CommandParser — per-instance registry
# ---------------------------------------------------------------------------

class CommandParser:
    """A self-contained command parser with its own registry."""

    def __init__(
        self,
        prefix: str = "/",
        debug: bool = False,
        dry_run: bool = False,
        hybrid: bool = True,
    ) -> None:
        self.registry: CommandRegistry = CommandRegistry()
        self.debug: bool = debug
        self.dry_run: bool = dry_run
        self.hybrid: bool = hybrid
        self.prefix: str = prefix
        self._var_store: VariableStore = VariableStore()
        self._permission_checker: PermissionChecker = PermissionChecker()
        self._middleware: MiddlewareChain = MiddlewareChain()
        self._pipeline: AsyncPipeline = AsyncPipeline()
        self._parser_instance = None  # lazy init

    def _get_parser(self):
        from .parser.executor import Parser as _Parser
        if self._parser_instance is None:
            self._parser_instance = _Parser(
                registry=self.registry,
                var_store=self._var_store,
                permission_checker=self._permission_checker,
                middleware_chain=self._middleware,
                pipeline=self._pipeline,
                debug=self.debug,
            )
        return self._parser_instance

    # ------------------------------------------------------------------
    # Decorator methods
    # ------------------------------------------------------------------

    def command(
        self,
        name: str,
        *,
        aliases: Optional[List[str]] = None,
        help: str = "",
        is_event: bool = False,
        hidden: bool = False,
        rate_limit: Optional[float] = None,
    ) -> Callable:
        """Decorator: register a command on this parser instance."""
        def decorator(fn: Callable) -> Callable:
            cmd = _get_or_create_cmd(self.registry, name)
            cmd.handler = fn
            cmd.aliases = aliases or []
            cmd.help = help or fn.__doc__ or ""
            cmd.is_event = is_event
            cmd.hidden = hidden
            if rate_limit is not None:
                cmd.rate_limit = rate_limit
            _collect_pending(fn, cmd)
            _infer_args_from_hints(cmd, fn)
            self.registry.register(cmd)
            fn._cmd_info = cmd  # type: ignore[attr-defined]
            return fn
        return decorator

    def arg(self, name: str, **kwargs: Any) -> Callable:
        """Decorator: stage an argument on the next @command."""
        return arg(name, **kwargs)

    def permission(self, *perms: str) -> Callable:
        """Decorator: require permissions on the next @command."""
        return permission(*perms)

    def middleware(self, *, before: Optional[Callable] = None, after: Optional[Callable] = None) -> Callable:
        """Decorator: attach command-level middleware to the next @command."""
        return middleware(before=before, after=after)

    def validator(self, fn_validator: Callable) -> Callable:
        """Decorator: stage a custom validator on the next @command."""
        return validator(fn_validator)

    def default_command(self, fn: Callable) -> Callable:
        """Register *fn* as the default text handler for this parser."""
        self.registry.set_default(fn)
        return fn

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        input_str: str,
        ctx: Optional["ExecutionContext"] = None,
    ) -> "CommandResult":
        """Async execute *input_str*."""
        from .core.context import ExecutionContext as _Ctx
        if ctx is None:
            ctx = _Ctx(dry_run=self.dry_run, debug=self.debug)
        return await self._get_parser().execute(input_str, ctx)

    def __call__(
        self,
        input_str: str,
        ctx: Optional["ExecutionContext"] = None,
    ) -> "CommandResult":
        """Synchronous execute wrapper."""
        return asyncio.run(self.execute(input_str, ctx))

    def loop(self, prompt: str = "> ", ctx: Optional["ExecutionContext"] = None):
        """Interactive sync loop — yields :class:`CommandResult` objects."""
        from .core.context import ExecutionContext as _Ctx
        if ctx is None:
            ctx = _Ctx()
        while True:
            try:
                line = input(prompt)
                result = asyncio.run(self.execute(line, ctx))
                yield result
            except EOFError:
                break
            except KeyboardInterrupt:
                print("\nInterrupt. Exiting...")
                break

    async def async_loop(self, prompt: str = "> ", ctx: Optional["ExecutionContext"] = None):
        """Async interactive loop — yields :class:`CommandResult` objects."""
        from .core.context import ExecutionContext as _Ctx
        import sys
        if ctx is None:
            ctx = _Ctx()
        while True:
            try:
                if sys.stdin.isatty():
                    line = input(prompt)
                else:
                    line = sys.stdin.readline()
                    if not line:
                        break
                    line = line.rstrip("\n")
                result = await self.execute(line, ctx)
                yield result
            except (EOFError, KeyboardInterrupt):
                break

    # ------------------------------------------------------------------
    # Help
    # ------------------------------------------------------------------

    def help(self, cmd_name: Optional[str] = None) -> str:
        """Return a help string for *cmd_name* or all commands."""
        if cmd_name:
            cmd = self.registry.get(cmd_name)
            if cmd is None:
                return f"Unknown command: {cmd_name!r}"
            lines = [f"/{cmd.name}"]
            if cmd.help:
                lines.append(f"  {cmd.help}")
            for a in cmd.args:
                req = "required" if a.required else f"optional, default={a.default!r}"
                lines.append(f"  --{a.name}  ({a.type.__name__}, {req})  {a.help}")
            return "\n".join(lines)
        lines = ["Available commands:"]
        for cmd in self.registry.all_commands():
            if not cmd.hidden:
                lines.append(f"  /{cmd.name:<20} {cmd.help}")
        return "\n".join(lines)

    def print_help(self, cmd_name: Optional[str] = None) -> None:
        """Print help to stdout."""
        print(self.help(cmd_name))

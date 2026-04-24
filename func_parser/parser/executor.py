"""Main parser / executor for func_parser."""
from __future__ import annotations

import asyncio
import re
import shlex
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..core.context import ExecutionContext
from ..core.errors import (
    CommandNotFoundError,
    InvalidArgError,
    MissingArgError,
    PermissionDeniedError,
    RateLimitError,
    ParseError,
)
from ..core.models import CommandInfo, CommandResult, OutputRedirect
from ..core.validation import coerce_type, validate_arg
from .ast_nodes import (
    ASTNode, AndNode, CommandNode, ExecuteScriptNode, IfNode,
    OrNode, PipelineNode, SetVarNode, TextNode,
)
from .tokenizer import Token, TokenType, Tokenizer

if TYPE_CHECKING:
    from ..core.middleware import MiddlewareChain
    from ..core.permissions import PermissionChecker
    from ..core.pipeline import AsyncPipeline
    from ..core.registry import CommandRegistry
    from ..core.variables import VariableStore

__all__ = ["Parser"]


class Parser:
    """Main engine: parses input strings into AST nodes and executes them."""

    def __init__(
        self,
        registry: "CommandRegistry",
        var_store: "VariableStore",
        permission_checker: "PermissionChecker",
        middleware_chain: "MiddlewareChain",
        pipeline: "AsyncPipeline",
        io_handler: Any = None,
        debug: bool = False,
    ) -> None:
        self._registry = registry
        self._vars = var_store
        self._permissions = permission_checker
        self._middleware = middleware_chain
        self._pipeline = pipeline
        self._io = io_handler
        self.debug = debug
        self._tokenizer = Tokenizer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, input_str: str) -> ASTNode:
        """Parse *input_str* into an AST node."""
        # Variable substitution before parsing
        expanded = self._vars.expand(input_str)
        tokens = self._tokenizer.tokenize(expanded)
        return self._parse_tokens(tokens, expanded)

    async def execute(self, input_str: str, ctx: ExecutionContext) -> CommandResult:
        """Parse *input_str* and execute the resulting AST node."""
        try:
            node = self.parse(input_str)
        except Exception as exc:
            return CommandResult(
                name="parse_error",
                args={},
                status="error",
                error=exc,
            )
        return await self.execute_node(node, ctx)

    async def execute_node(self, node: ASTNode, ctx: ExecutionContext) -> CommandResult:
        """Execute a single AST node."""
        if isinstance(node, TextNode):
            return await self._execute_text(node, ctx)
        elif isinstance(node, CommandNode):
            return await self._execute_command(node, ctx)
        elif isinstance(node, PipelineNode):
            return await self._execute_pipeline(node, ctx)
        elif isinstance(node, AndNode):
            return await self._execute_and(node, ctx)
        elif isinstance(node, OrNode):
            return await self._execute_or(node, ctx)
        elif isinstance(node, SetVarNode):
            return await self._execute_set_var(node, ctx)
        elif isinstance(node, ExecuteScriptNode):
            results = await self.execute_script(node.path, ctx)
            last = results[-1] if results else CommandResult("execute", {}, "success")
            return last
        elif isinstance(node, IfNode):
            return await self._execute_if(node, ctx)
        return CommandResult("unknown", {}, "unknown")

    async def execute_script(self, path: str, ctx: ExecutionContext) -> List[CommandResult]:
        """Execute a script file line by line."""
        results: List[CommandResult] = []
        try:
            with open(path, encoding="utf-8") as fh:
                lines = fh.readlines()
        except OSError as exc:
            return [CommandResult("execute", {"path": path}, "error", error=exc)]
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            result = await self.execute(line, ctx)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Token → AST
    # ------------------------------------------------------------------

    def _parse_tokens(self, tokens: List[Token], raw: str) -> ASTNode:
        """Convert a token list into an AST node."""
        # Filter EOF / comment tokens
        meaningful = [t for t in tokens if t.type not in (TokenType.EOF, TokenType.COMMENT)]
        if not meaningful:
            return TextNode(raw)

        # Check for &&  / ||  operators (lowest precedence, left-to-right)
        node = self._parse_logical(meaningful, raw)
        return node

    def _parse_logical(self, tokens: List[Token], raw: str) -> ASTNode:
        """Parse && / || binary operators."""
        # Find rightmost && or || at the top level
        for i in range(len(tokens) - 1, -1, -1):
            if tokens[i].type == TokenType.AND:
                left = self._parse_pipeline(tokens[:i], raw)
                right = self._parse_logical(tokens[i+1:], raw)
                return AndNode(left=left, right=right)
            if tokens[i].type == TokenType.OR:
                left = self._parse_pipeline(tokens[:i], raw)
                right = self._parse_logical(tokens[i+1:], raw)
                return OrNode(left=left, right=right)
        return self._parse_pipeline(tokens, raw)

    def _parse_pipeline(self, tokens: List[Token], raw: str) -> ASTNode:
        """Parse | operators into a PipelineNode or single CommandNode."""
        # Split on PIPE
        segments: List[List[Token]] = []
        current: List[Token] = []
        for tok in tokens:
            if tok.type == TokenType.PIPE:
                segments.append(current)
                current = []
            else:
                current.append(tok)
        segments.append(current)

        if len(segments) == 1:
            return self._parse_single(segments[0], raw)

        commands: List[CommandNode] = []
        for seg in segments:
            node = self._parse_single(seg, raw)
            if isinstance(node, CommandNode):
                commands.append(node)
            else:
                # Wrap non-command in a dummy command (best-effort)
                commands.append(CommandNode(name=raw))
        return PipelineNode(commands=commands)

    def _parse_single(self, tokens: List[Token], raw: str) -> ASTNode:
        """Parse a single command/directive/text from a token list."""
        if not tokens:
            return TextNode("")

        first = tokens[0]

        # //set or //setenv
        if first.type == TokenType.SET_VAR:
            return self._parse_set_var(tokens)

        # /execute
        if first.type == TokenType.EXECUTE:
            path = tokens[1].value if len(tokens) > 1 else ""
            return ExecuteScriptNode(path=path)

        # Regular command
        if first.type == TokenType.COMMAND:
            return self._parse_command(tokens)

        # Plain text → TextNode
        return TextNode(raw)

    def _parse_set_var(self, tokens: List[Token]) -> SetVarNode:
        """Parse a ``//set`` / ``//setenv`` directive."""
        directive = tokens[0].value.lower()
        scope = "env" if directive == "//setenv" else "local"
        assignment = tokens[1].value if len(tokens) > 1 else ""
        if "=" in assignment:
            name, _, value = assignment.partition("=")
        else:
            name = assignment
            value = ""
        return SetVarNode(name=name.strip(), value=value.strip(), scope=scope)

    def _parse_command(self, tokens: List[Token]) -> CommandNode:
        """Parse a command token list into a :class:`CommandNode`."""
        name = tokens[0].value.lstrip("/")
        args: List[str] = []
        kwargs: Dict[str, str] = {}
        redirect: Optional[OutputRedirect] = None

        i = 1
        while i < len(tokens):
            tok = tokens[i]
            if tok.type == TokenType.REDIRECT_OUT:
                i += 1
                target = tokens[i].value if i < len(tokens) else "stdout"
                redirect = OutputRedirect(target=target, append=False)
            elif tok.type == TokenType.REDIRECT_APPEND:
                i += 1
                target = tokens[i].value if i < len(tokens) else "stdout"
                redirect = OutputRedirect(target=target, append=True)
            elif tok.type == TokenType.REDIRECT_CLIPBOARD:
                append = tok.value.startswith(">>")
                redirect = OutputRedirect(target="clipboard", append=append)
            elif tok.type == TokenType.ARG:
                val = tok.value
                if "=" in val and not val.startswith("{") and not val.startswith('"'):
                    k, _, v = val.partition("=")
                    kwargs[k] = v
                else:
                    args.append(val)
            i += 1

        return CommandNode(name=name, args=args, kwargs=kwargs, redirect=redirect)

    # ------------------------------------------------------------------
    # Execution helpers
    # ------------------------------------------------------------------

    async def _execute_text(self, node: TextNode, ctx: ExecutionContext) -> CommandResult:
        """Route plain text to the default handler."""
        handler = self._registry.default_handler
        if handler is None:
            return CommandResult("default", {"text": node.content}, "success", output=None)
        try:
            import inspect
            sig = inspect.signature(handler)
            params = list(sig.parameters.keys())
            if params and params[0] == "ctx":
                call = handler(ctx, node.content)
            else:
                call = handler(node.content)
            if asyncio.iscoroutine(call):
                output = await call
            else:
                output = call
            return CommandResult("default", {"text": node.content}, "success", output=output)
        except Exception as exc:
            return CommandResult("default", {"text": node.content}, "error", error=exc)

    async def _execute_command(self, node: CommandNode, ctx: ExecutionContext) -> CommandResult:
        """Resolve and execute a :class:`CommandNode`."""
        cmd_info = self._registry.get(node.name)
        if cmd_info is None:
            err = CommandNotFoundError(node.name)
            return CommandResult(node.name, {}, "unknown", error=err)

        # Permission check
        try:
            self._permissions.require(
                ctx.user.roles,
                cmd_info.permissions,
                ctx.user.id,
            )
        except PermissionDeniedError as exc:
            return CommandResult(node.name, {}, "permission_denied", error=exc)

        # Rate limit check
        try:
            self._middleware.check_rate_limit(node.name)
        except RateLimitError as exc:
            return CommandResult(node.name, {}, "error", error=exc)

        # Build args dict
        try:
            parsed_args = self._build_args(node, cmd_info, ctx)
        except (MissingArgError, InvalidArgError) as exc:
            status = "missing_args" if isinstance(exc, MissingArgError) else "invalid_args"
            return CommandResult(node.name, {}, status, error=exc)

        # Before-middleware
        try:
            parsed_args = await self._middleware.run_before(ctx, node.name, parsed_args)
        except Exception as exc:
            return CommandResult(node.name, parsed_args, "error", error=exc)

        # Command-specific before-middleware
        for mw_fn in cmd_info.middleware_before:
            try:
                result_args = mw_fn(ctx, node.name, parsed_args)
                if asyncio.iscoroutine(result_args):
                    result_args = await result_args
                if isinstance(result_args, dict):
                    parsed_args = result_args
            except Exception as exc:
                return CommandResult(node.name, parsed_args, "error", error=exc)

        # Execute
        result = await self._pipeline.execute(cmd_info, parsed_args, ctx)
        result.redirect = node.redirect

        # After-middleware
        result = await self._middleware.run_after(ctx, result)

        # Command-specific after-middleware
        for mw_fn in cmd_info.middleware_after:
            try:
                r = mw_fn(ctx, result)
                if asyncio.iscoroutine(r):
                    r = await r
                if isinstance(r, CommandResult):
                    result = r
            except Exception:
                pass

        # Handle output redirection
        if result.redirect:
            await self._pipeline.redirect_output(result, result.redirect)

        if self.debug:
            print(f"[DEBUG] {result}")
        return result

    async def _execute_pipeline(self, node: PipelineNode, ctx: ExecutionContext) -> CommandResult:
        """Execute a pipeline: pass output of each command to the next."""
        last: Optional[CommandResult] = None
        injected_arg: Optional[str] = None
        for cmd_node in node.commands:
            if injected_arg is not None:
                # Prepend injected arg
                cmd_node = CommandNode(
                    name=cmd_node.name,
                    args=[injected_arg] + list(cmd_node.args),
                    kwargs=cmd_node.kwargs,
                    redirect=cmd_node.redirect,
                )
            last = await self._execute_command(cmd_node, ctx)
            if last.output is not None:
                injected_arg = str(last.output)
            else:
                injected_arg = None
        return last or CommandResult("pipeline", {}, "success")

    async def _execute_and(self, node: AndNode, ctx: ExecutionContext) -> CommandResult:
        """Execute ``left && right``: run right only if left succeeds."""
        left_result = await self.execute_node(node.left, ctx)
        if not left_result.ok:
            return left_result
        return await self.execute_node(node.right, ctx)

    async def _execute_or(self, node: OrNode, ctx: ExecutionContext) -> CommandResult:
        """Execute ``left || right``: run right only if left fails."""
        left_result = await self.execute_node(node.left, ctx)
        if left_result.ok:
            return left_result
        return await self.execute_node(node.right, ctx)

    async def _execute_set_var(self, node: SetVarNode, ctx: ExecutionContext) -> CommandResult:
        """Handle ``//set`` and ``//setenv``."""
        self._vars.set(node.name, node.value, scope=node.scope)
        ctx.set_var(node.name, node.value)
        return CommandResult(
            "set_var",
            {"name": node.name, "value": node.value, "scope": node.scope},
            "success",
        )

    async def _execute_if(self, node: IfNode, ctx: ExecutionContext) -> CommandResult:
        """Execute a basic IfNode (condition is a variable/expression string)."""
        condition_val = self._vars.get(node.condition, "false")
        truthy = str(condition_val).lower() not in ("", "0", "false", "no", "none")
        branch = node.body if truthy else node.else_body
        if branch is not None:
            return await self.execute_node(branch, ctx)
        return CommandResult("if", {}, "success")

    # ------------------------------------------------------------------
    # Arg binding
    # ------------------------------------------------------------------

    def _build_args(
        self,
        node: CommandNode,
        cmd_info: CommandInfo,
        ctx: ExecutionContext,
    ) -> Dict[str, Any]:
        """Bind raw tokens to the command's :class:`ArgDef` schema."""
        result: Dict[str, Any] = {}
        positional_raw = list(node.args)
        pos_idx = 0

        for arg_def in cmd_info.args:
            # keyword arg override
            if arg_def.name in node.kwargs:
                raw_val = node.kwargs[arg_def.name]
            elif arg_def.variadic:
                # Collect remaining positional args
                remaining = positional_raw[pos_idx:]
                expanded = [self._expand_file_arg(v, ctx) for v in remaining]
                coerced = []
                for rv in expanded:
                    cv = coerce_type(rv, arg_def)
                    coerced.append(validate_arg(arg_def.name, cv, arg_def))
                result[arg_def.name] = coerced
                pos_idx = len(positional_raw)
                continue
            elif pos_idx < len(positional_raw):
                raw_val = positional_raw[pos_idx]
                pos_idx += 1
            elif not arg_def.required:
                result[arg_def.name] = arg_def.default
                continue
            else:
                raise MissingArgError(arg_def.name, cmd_info.name)

            # Expand {file} args
            raw_val = self._expand_file_arg(raw_val, ctx)
            # Coerce and validate
            coerced = coerce_type(raw_val, arg_def)
            result[arg_def.name] = validate_arg(arg_def.name, coerced, arg_def)

        return result

    def _expand_file_arg(self, val: str, ctx: ExecutionContext) -> str:
        """If *val* is a ``{file.txt}`` marker, return the file contents."""
        if val.startswith("{") and val.endswith("}"):
            path = val[1:-1]
            try:
                with open(path, encoding="utf-8") as fh:
                    return fh.read()
            except OSError:
                return val  # leave as-is if file not found
        return val

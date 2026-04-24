"""Async execution pipeline for func_parser."""
from __future__ import annotations

import asyncio
from typing import Any, List, Optional

from .context import ExecutionContext
from .models import CommandInfo, CommandResult, OutputRedirect

__all__ = ["AsyncPipeline"]


class AsyncPipeline:
    """Executes command handlers asynchronously and handles output redirection."""

    async def execute(
        self,
        cmd_info: CommandInfo,
        args: dict,
        ctx: ExecutionContext,
    ) -> CommandResult:
        """Call the handler (sync or async) and return a :class:`CommandResult`.

        In *dry_run* mode the handler is not called; a ``"dry_run"`` status is returned instead.
        """
        if ctx.dry_run:
            return CommandResult(
                name=cmd_info.name,
                args=args,
                status="dry_run",
                is_event=cmd_info.is_event,
            )

        if cmd_info.is_event:
            return CommandResult(
                name=cmd_info.name,
                args=args,
                status="success",
                is_event=True,
            )

        handler = cmd_info.handler
        if handler is None:
            return CommandResult(
                name=cmd_info.name,
                args=args,
                status="error",
                error=RuntimeError(f"Command {cmd_info.name!r} has no handler"),
            )

        try:
            # Pass ctx only if the handler accepts it
            import inspect
            sig = inspect.signature(handler)
            params = list(sig.parameters.keys())
            if params and params[0] == "ctx":
                call_args = {"ctx": ctx, **args}
            else:
                call_args = args

            if asyncio.iscoroutinefunction(handler):
                output = await handler(**call_args)
            else:
                output = handler(**call_args)

            return CommandResult(
                name=cmd_info.name,
                args=args,
                status="success",
                output=output,
                is_event=cmd_info.is_event,
            )
        except Exception as exc:
            return CommandResult(
                name=cmd_info.name,
                args=args,
                status="error",
                error=exc,
            )

    async def run_pipeline(
        self,
        steps: List[tuple],  # list of (cmd_info, args, ctx)
        ctx: ExecutionContext,
    ) -> Any:
        """Execute a pipeline of commands, piping output of each to the next.

        Returns the output of the final command.
        """
        last_output: Any = None
        for i, (cmd_info, args) in enumerate(steps):
            if i > 0 and last_output is not None:
                # Inject previous output as first positional arg
                if cmd_info.args:
                    first_arg_name = cmd_info.args[0].name
                    args = {first_arg_name: str(last_output), **args}
            result = await self.execute(cmd_info, args, ctx)
            last_output = result.output
        return last_output

    async def redirect_output(
        self,
        result: CommandResult,
        redirect: OutputRedirect,
    ) -> None:
        """Write *result.output* to the redirect target (file or clipboard)."""
        text = str(result.output) if result.output is not None else ""
        if redirect.is_clipboard:
            try:
                import pyperclip  # type: ignore
                pyperclip.copy(text)
            except ImportError:
                pass  # silently skip if pyperclip not installed
        elif redirect.is_file:
            mode = "a" if redirect.append else "w"
            with open(redirect.target, mode, encoding="utf-8") as fh:
                fh.write(text)

"""
cli_example.py — Interactive CLI built with func_parser + prompt_toolkit.

Demonstrates:
- CLIAdapter (prompt_toolkit)
- Fallback to basic input when prompt_toolkit is not installed
- Commands, aliases, permissions, middleware, pipeline
- Redirect output to a file
"""
import asyncio

from func_parser import (
    CommandParser, ExecutionContext, User, arg, permission, middleware,
)
from func_parser.adapters.cli import CLIAdapter


parser = CommandParser(hybrid=True, debug=False)

# ---------------------------------------------------------------------------
# Middleware: log every command
# ---------------------------------------------------------------------------

@parser._middleware.before
def log_cmd(ctx, cmd_name, args):
    print(f"  [log] executing {cmd_name!r} args={args}")
    return args


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@parser.command("echo", help="Echo arguments back to stdout")
@arg("text", type=str, variadic=True, help="Text to echo")
async def cmd_echo(ctx, text):
    return " ".join(str(t) for t in text)


@parser.command("upper", help="Convert text to uppercase")
@arg("text", type=str, required=True)
async def cmd_upper(ctx, text: str):
    return text.upper()


@parser.command("lower", help="Convert text to lowercase")
@arg("text", type=str, required=True)
async def cmd_lower(ctx, text: str):
    return text.lower()


@parser.command("reverse", help="Reverse a string")
@arg("text", type=str, required=True)
async def cmd_reverse(ctx, text: str):
    return text[::-1]


@parser.command("len", aliases=["length"], help="Return the length of text")
@arg("text", type=str, required=True)
async def cmd_len(ctx, text: str):
    return len(text)


@parser.command("add", help="Add two numbers")
@arg("a", type=float)
@arg("b", type=float)
async def cmd_add(ctx, a: float, b: float):
    return a + b


@parser.command("quit", aliases=["exit", "q"], help="Quit the CLI")
async def cmd_quit(ctx):
    raise SystemExit(0)


@parser.command("help", aliases=["h", "?"], help="Show this help message")
async def cmd_help(ctx):
    return parser.help()


# Admin-only command
@parser.command("secret", help="Admin-only command")
@permission("admin")
async def cmd_secret(ctx):
    return "🔐 Top secret info!"


# ---------------------------------------------------------------------------
# Default text handler
# ---------------------------------------------------------------------------

@parser.default_command
async def on_text(ctx, content: str):
    return f"(not a command) {content!r}"


# ---------------------------------------------------------------------------
# Demo run — runs a fixed batch of inputs (non-interactive)
# ---------------------------------------------------------------------------

async def demo():
    ctx = ExecutionContext(user=User(id="admin1", roles=["admin"]))
    print("=== CLI Example (demo mode) ===\n")

    commands = [
        "/echo hello world",
        "/upper hello",
        "/upper hello | /reverse",    # pipeline
        "/len testing",
        "/add 10 32",
        "plain text input",
        "/secret",
        "/help",
    ]

    for line in commands:
        print(f"> {line}")
        result = await parser.execute(line, ctx)
        if result.output is not None:
            print(result.output)
        elif result.error:
            print(f"Error: {result.error}")
        print()


# ---------------------------------------------------------------------------
# Interactive mode (requires prompt_toolkit)
# ---------------------------------------------------------------------------

async def interactive():
    ctx = ExecutionContext(user=User(id="user1", roles=["admin"]))
    adapter = CLIAdapter(parser, prompt="cli> ", ctx=ctx)
    await adapter.run()


if __name__ == "__main__":
    import sys
    if "--interactive" in sys.argv:
        asyncio.run(interactive())
    else:
        asyncio.run(demo())

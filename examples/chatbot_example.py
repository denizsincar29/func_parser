"""
chatbot_example.py — Simple chatbot using func_parser.

Demonstrates:
- @command decorator
- @default_command for free-text input
- async handlers
- ExecutionContext / User
- Running a one-shot execute loop
"""
import asyncio

from func_parser import CommandParser, ExecutionContext, User, arg


parser = CommandParser(hybrid=True)


# ---------------------------------------------------------------------------
# Registered commands
# ---------------------------------------------------------------------------

@parser.command("help", aliases=["h"], help="Show available commands")
async def cmd_help(ctx):
    return parser.help()


@parser.command("greet", help="Greet a user by name")
@arg("name", type=str, required=True, help="Name to greet")
async def cmd_greet(ctx, name: str):
    return f"Hello, {name}! Nice to meet you. 👋"


@parser.command("add", help="Add two numbers")
@arg("a", type=float, required=True)
@arg("b", type=float, required=True)
async def cmd_add(ctx, a: float, b: float):
    return f"{a} + {b} = {a + b}"


@parser.command("remember", help="Store a value: /remember key=value")
@arg("key", type=str, required=True)
@arg("value", type=str, required=True)
async def cmd_remember(ctx, key: str, value: str):
    ctx.set_var(key, value)
    return f"I'll remember that {key} = {value}."


@parser.command("recall", help="Recall a stored value: /recall key")
@arg("key", type=str, required=True)
async def cmd_recall(ctx, key: str):
    val = ctx.get_var(key)
    if val is None:
        return f"I don't remember anything about '{key}'."
    return f"{key} = {val}"


# ---------------------------------------------------------------------------
# Default handler for free-form text
# ---------------------------------------------------------------------------

@parser.default_command
async def on_text(ctx, content: str):
    """Echo back whatever the user types (simulating a chatbot reply)."""
    return f"🤖 You said: '{content}'. (Try /help for commands)"


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def main():
    ctx = ExecutionContext(user=User(id="user1", name="Alice"))
    print("=== Chatbot Example ===")
    print("Type messages or /commands. Ctrl-C / Ctrl-D to quit.\n")

    inputs = [
        "hello there",
        "/greet Bob",
        "/add 3.5 6.5",
        "/remember color blue",
        "/recall color",
        "/help",
    ]

    for line in inputs:
        print(f"> {line}")
        result = await parser.execute(line, ctx)
        if result.output is not None:
            print(result.output)
        if result.error and not result.ok:
            print(f"Error: {result.error}")
        print()


if __name__ == "__main__":
    asyncio.run(main())

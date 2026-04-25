"""
sync_async_example.py — Complete demo of sync and async execution in func_parser.

Covers:
- async execute / execute_sync / __call__
- async_loop and sync loop
- pipeline, &&, ||
- variables (//set / ${var})
- output redirection
- permissions
- middleware (before/after)
- rate limiting
- dry-run mode
- @validator decorator
- @arg with ranges, regex, presets
- variadic args
- namespace commands (user.create / user.list)
- @default_command
- Scheduler (parse_spec only — no background tasks in demo)
"""
import asyncio

from func_parser import (
    CommandParser,
    ExecutionContext,
    User,
    arg,
    permission,
    middleware,
    validator,
)
from func_parser.scheduler import Scheduler


# ===========================================================================
# Build parser
# ===========================================================================
parser = CommandParser(hybrid=True, debug=False)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
log_lines: list = []

@parser._middleware.before
def log_before(ctx, cmd_name, args):
    log_lines.append(f"before:{cmd_name}")
    return args

@parser._middleware.after
def log_after(ctx, result):
    log_lines.append(f"after:{result.name}={result.status}")
    return result


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@parser.command("greet", aliases=["g"], help="Greet someone")
@arg("name", type=str, required=True)
async def cmd_greet(ctx, name: str):
    return f"Hello, {name}!"


@parser.command("add", help="Add two numbers")
@arg("a", type=float, required=True)
@arg("b", type=float, required=True)
async def cmd_add(ctx, a: float, b: float):
    return a + b


@parser.command("upper", help="Uppercase a string")
@arg("text", type=str, required=True)
async def cmd_upper(ctx, text: str):
    return text.upper()


@parser.command("reverse", help="Reverse a string")
@arg("text", type=str, required=True)
async def cmd_reverse(ctx, text: str):
    return text[::-1]


@parser.command("echo", help="Echo all arguments")
@arg("words", type=str, variadic=True)
async def cmd_echo(ctx, words):
    return " ".join(str(w) for w in words)


@parser.command("age_check", help="Check age is 18-120")
@arg("age", type=int, min=18, max=120)
async def cmd_age(ctx, age: int):
    return f"Age {age} is valid"


@parser.command("email_check", help="Validate an email address")
@arg("email", type=str, preset="email")
async def cmd_email(ctx, email: str):
    return f"Email {email} is valid"


@parser.command("validated", help="Command with custom @validator")
@arg("code", type=str, required=True)
@validator
async def validate_code(ctx, args):
    if args.get("code", "").upper() != args.get("code", ""):
        raise ValueError("code must be uppercase")
    return args

async def validated_handler(ctx, code: str):
    return f"Code accepted: {code}"

# manually register handler after validator
parser.registry.get("validated").handler = validated_handler


@parser.command("secret", help="Admin-only command")
@permission("admin")
async def cmd_secret(ctx):
    return "top secret"


@parser.command("limited", help="Rate-limited command (max 2 per window)")
async def cmd_limited(ctx):
    return "ok"

parser._middleware.set_rate_limit("limited", max_calls=2, window_secs=60.0)


# Namespace commands
@parser.command("user.create", aliases=["uc"], help="Create a user")
@arg("name", type=str, required=True)
async def cmd_user_create(ctx, name: str):
    return f"User '{name}' created"


@parser.command("user.list", aliases=["ul"], help="List users")
async def cmd_user_list(ctx):
    return "alice, bob, charlie"


@parser.default_command
async def on_text(ctx, content: str):
    return f"[text] {content}"


# ===========================================================================
# Execution contexts
# ===========================================================================
admin_ctx = ExecutionContext(user=User(id="admin1", roles=["admin"]))
user_ctx  = ExecutionContext(user=User(id="user1",  roles=["user"]))


# ===========================================================================
# Helpers
# ===========================================================================
def show(label: str, result):
    status = "✓" if result.ok else f"✗({result.status})"
    print(f"  {status}  {label:<40} → {result.output or result.error}")


# ===========================================================================
# 1. ASYNC mode
# ===========================================================================
async def demo_async():
    print("\n═══ ASYNC execution ═══\n")

    ctx = admin_ctx

    # Basic commands
    show("/greet Alice",            await parser.execute("/greet Alice",          ctx))
    show("/add 10.5 31.5",          await parser.execute("/add 10.5 31.5",        ctx))
    show("/echo hello world foo",   await parser.execute("/echo hello world foo", ctx))

    # Pipeline
    show("/upper hello | /reverse", await parser.execute("/upper hello | /reverse", ctx))

    # && / ||
    show("/greet A && /greet B",    await parser.execute("/greet A && /greet B",   ctx))
    show("/nonexist || /greet C",   await parser.execute("/nonexist || /greet C",  ctx))

    # Variables
    await parser.execute("//set greeting=Hi", ctx)
    show("/greet ${greeting}",      await parser.execute("/greet ${greeting}",     ctx))

    # Arg validation
    show("/age_check 25",           await parser.execute("/age_check 25",          ctx))
    show("/age_check 5 (invalid)",  await parser.execute("/age_check 5",           ctx))
    show("/email_check a@b.com",    await parser.execute("/email_check a@b.com",   ctx))

    # Namespace
    show("/user.create Dave",       await parser.execute("/user.create Dave",      ctx))
    show("/ul (alias)",             await parser.execute("/ul",                    ctx))

    # Permissions
    show("/secret (admin)",         await parser.execute("/secret",                admin_ctx))
    show("/secret (user→denied)",   await parser.execute("/secret",                user_ctx))

    # Rate limit
    await parser.execute("/limited", ctx)
    await parser.execute("/limited", ctx)
    show("/limited (3rd→ratelimit)",await parser.execute("/limited",               ctx))

    # Default text handler
    show("plain text",              await parser.execute("hello world",            ctx))

    # Dry run
    dry_ctx = ExecutionContext(user=User(roles=["admin"]), dry_run=True)
    show("/add 3 4 (dry-run)",      await parser.execute("/add 3 4",              dry_ctx))

    print(f"\n  Middleware log: {log_lines[:6]}…")


# ===========================================================================
# 2. SYNC mode
# ===========================================================================
def demo_sync():
    print("\n═══ SYNC execution ═══\n")

    ctx = admin_ctx

    show("/greet Bob",              parser.execute_sync("/greet Bob",           ctx))
    show("/add 7 8",                parser.execute_sync("/add 7 8",             ctx))
    show("plain text",              parser.execute_sync("plain text here",      ctx))
    show("/upper test | /reverse",  parser.execute_sync("/upper test | /reverse", ctx))
    show("//set x=42 + recall",     parser.execute_sync("//set x=42",           ctx))
    show("/echo ${x}",              parser.execute_sync("/echo ${x}",           ctx))

    # __call__ shorthand
    result = parser("/greet __call__", ctx)
    show("parser() call shorthand", result)


# ===========================================================================
# 3. SYNC loop (short batch)
# ===========================================================================
def demo_sync_loop():
    print("\n═══ SYNC loop (batch) ═══\n")
    ctx = admin_ctx
    batch = ["/greet loop1", "/add 1 2", "/upper looped"]
    gen = parser.loop(prompt="", ctx=ctx)
    # Inject lines without blocking on real stdin by monkey-patching builtins.input
    import builtins
    original_input = builtins.input
    batch_iter = iter(batch)

    def fake_input(prompt=""):
        try:
            return next(batch_iter)
        except StopIteration:
            raise EOFError

    builtins.input = fake_input
    try:
        for result in gen:
            show(result.name, result)
    finally:
        builtins.input = original_input


# ===========================================================================
# 4. ASYNC loop (batch)
# ===========================================================================
async def demo_async_loop():
    print("\n═══ ASYNC loop (batch) ═══\n")
    ctx = admin_ctx
    batch = ["/greet asyncloop", "/add 2 3", "text via async loop"]
    import builtins, sys
    original_input = builtins.input
    batch_iter = iter(batch)

    def fake_input(prompt=""):
        try:
            return next(batch_iter)
        except StopIteration:
            raise EOFError

    builtins.input = fake_input
    try:
        async for result in parser.async_loop(prompt="", ctx=ctx):
            show(result.name, result)
    finally:
        builtins.input = original_input


# ===========================================================================
# 5. Scheduler parse_spec
# ===========================================================================
def demo_scheduler():
    print("\n═══ Scheduler parse_spec ═══\n")
    s = Scheduler(execute_fn=lambda cmd: None)
    cases = [
        ("every 5s",  5.0),
        ("every 2m",  120.0),
        ("every 1h",  3600.0),
    ]
    for spec, expected in cases:
        got = s.parse_spec(spec)
        ok = "✓" if got == expected else "✗"
        print(f"  {ok}  parse_spec({spec!r}) = {got}")


# ===========================================================================
# 6. execute_sync from inside async context (nested loop simulation)
# ===========================================================================
async def demo_sync_inside_async():
    print("\n═══ execute_sync from async context ═══\n")
    # execute_sync must dispatch to a thread when the event loop is running
    result = parser.execute_sync("/greet FromSyncInsideAsync", admin_ctx)
    show("/greet FromSyncInsideAsync (sync-in-async)", result)


# ===========================================================================
# Main
# ===========================================================================
async def main():
    await demo_async()
    demo_sync()
    demo_sync_loop()
    await demo_async_loop()
    demo_scheduler()
    await demo_sync_inside_async()
    print("\n✅ All demos complete.\n")


if __name__ == "__main__":
    asyncio.run(main())

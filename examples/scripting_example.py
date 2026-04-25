"""
scripting_example.py — Script execution and variable system demo.

Demonstrates:
- //set / //setenv variable assignment
- ${var} / $VAR expansion
- /execute <script.txt> to run a script file
- && and || operators
- Pipeline composition
- Scheduling (non-blocking demo)
- Dry-run mode
"""
import asyncio
import os
import tempfile

from func_parser import CommandParser, ExecutionContext, User, arg


parser = CommandParser(hybrid=True)


# ---------------------------------------------------------------------------
# Commands used in the scripting demo
# ---------------------------------------------------------------------------

@parser.command("print", aliases=["p"], help="Print a value")
@arg("text", type=str, required=True)
async def cmd_print(ctx, text: str):
    print(f"  >> {text}")
    return text


@parser.command("double", help="Double a number")
@arg("n", type=int)
async def cmd_double(ctx, n: int):
    return n * 2


@parser.command("greet", help="Greet user")
@arg("name", type=str)
async def cmd_greet(ctx, name: str):
    return f"Hello, {name}!"


@parser.command("fail_example", help="Always fails (for || demo)")
async def cmd_fail(ctx):
    raise RuntimeError("intentional failure")


@parser.command("fallback", help="Fallback command")
async def cmd_fallback(ctx):
    return "fallback ran successfully"


# ---------------------------------------------------------------------------
# Helper to run and display a command
# ---------------------------------------------------------------------------

async def run(ctx, cmd, label=None):
    lbl = label or cmd
    result = await parser.execute(cmd, ctx)
    status = "✓" if result.ok else "✗"
    output = result.output if result.output is not None else result.error
    print(f"  {status} [{lbl}] → {output}")
    return result


# ---------------------------------------------------------------------------
# Main demo
# ---------------------------------------------------------------------------

async def main():
    print("=== Scripting Example ===\n")
    ctx = ExecutionContext(user=User(id="scripter", roles=["admin"]))

    # 1. Variable assignment and expansion
    print("── Variables ──")
    await run(ctx, "//set name=Alice")
    await run(ctx, "//set count=3")
    await run(ctx, "/greet ${name}")
    await run(ctx, "/double ${count}")
    print()

    # 2. Pipeline
    print("── Pipeline ──")
    await run(ctx, "/greet ${name} | /print", label="greet | print")
    print()

    # 3. && operator
    print("── && (and) ──")
    await run(ctx, "/greet Alice && /greet Bob", label="greet Alice && greet Bob")
    print()

    # 4. || operator (fallback on failure)
    print("── || (or / fallback) ──")
    await run(ctx, "/fail_example || /fallback", label="fail || fallback")
    print()

    # 5. Script file execution
    print("── Script file ──")
    script = (
        "//set x=7\n"
        "/double ${x}\n"
        "/greet Scripted\n"
        "# This is a comment — ignored\n"
        "/print done\n"
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(script)
        script_path = fh.name

    try:
        results = await parser._get_parser().execute_script(script_path, ctx)
        for r in results:
            status = "✓" if r.ok else "✗"
            print(f"  {status} {r.name} → {r.output or r.error}")
    finally:
        os.unlink(script_path)
    print()

    # 6. Dry-run mode
    print("── Dry-run mode ──")
    dry_ctx = ExecutionContext(user=User(id="scripter", roles=["admin"]), dry_run=True)
    dry_result = await parser.execute("/double 21", dry_ctx)
    print(f"  status={dry_result.status!r} (handler was not called)")
    print()

    # 7. Output redirection to a file
    print("── Output redirection ──")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as fh:
        out_path = fh.name

    try:
        await run(ctx, f"/greet Redirected > {out_path}", label=f"greet > {out_path}")
        with open(out_path, encoding="utf-8") as fh:
            content = fh.read()
        print(f"  File contents: {content!r}")
    finally:
        os.unlink(out_path)


if __name__ == "__main__":
    asyncio.run(main())

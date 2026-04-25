# func_parser

A **modular, extensible command/function parser** written in Python (with a companion Rust crate).  
Built as a **core engine**, not a CLI-first tool — the CLI is just one adapter.

---

## Features

| Feature | Status |
|---------|--------|
| Command model (positional, named, variadic, defaults) | ✅ |
| Clean decorator API (`@command`, `@arg`, `@validator`, `@permission`, `@middleware`) | ✅ |
| Default text handler (`@default_command`) | ✅ |
| Hybrid mode — commands + free text in the same parser | ✅ |
| Argument types, ranges, regex, presets (email, url, phone) | ✅ |
| Pipeline operator `\|` | ✅ |
| `&&` / `\|\|` control flow | ✅ |
| Variables: `//set`, `//setenv`, `${var}`, `$VAR` | ✅ |
| Output redirection `>`, `>>`, `>clipboard` | ✅ |
| File argument injection `{file.txt}` | ✅ |
| Script execution `/execute script.txt` | ✅ |
| Namespaces (`user.create`, `file.read`) | ✅ |
| Async-first execution pipeline | ✅ |
| Middleware (global before/after + per-command) | ✅ |
| Permission system (roles + per-user grants) | ✅ |
| Rate limiting | ✅ |
| Scheduler (`every 5m`, `at 12:00`) | ✅ |
| Dry-run mode | ✅ |
| Undo / redo (context history) | ✅ |
| Plugin system | ✅ |
| I/O abstraction (stdin, stdout, file, clipboard) | ✅ |
| CLI adapter (prompt_toolkit) | ✅ |
| Control-flow DSL: `if` / `while` nodes | ✅ |
| AST debug mode | ✅ |
| Auto help from type hints | ✅ |
| **Rust core engine** (`func_parser_rs/`) | ✅ |

---

## Installation

```bash
pip install -e .
```

For the optional CLI adapter (autocompletion, syntax highlighting):

```bash
pip install prompt_toolkit
```

For clipboard support:

```bash
pip install pyperclip
```

---

## Quick Start

```python
import asyncio
from func_parser import CommandParser, ExecutionContext, User, arg

parser = CommandParser(hybrid=True)

@parser.command("greet", aliases=["g"], help="Greet someone")
@arg("name", type=str, required=True)
async def greet(ctx, name: str):
    return f"Hello, {name}!"

@parser.default_command
async def on_text(ctx, content: str):
    return f"You said: {content!r}"

async def main():
    ctx = ExecutionContext(user=User(id="alice", roles=["admin"]))
    print(await parser.execute("/greet World", ctx))  # Hello, World!
    print(await parser.execute("plain text", ctx))    # You said: 'plain text'

asyncio.run(main())
```

---

## Decorator API

```python
from func_parser import command, arg, validator, permission, middleware

@command("user.create", aliases=["uc"])
@arg("name", type=str, required=True, help="User name")
@arg("age",  type=int, min=0, max=150, default=0)
@permission("admin")
async def create_user(ctx, name: str, age: int):
    ...
```

### `@command(name, aliases=[], help="", rate_limit=None, hidden=False)`

Registers an async (or sync) function as a command.

### `@arg(name, type=str, required=True, default=None, variadic=False, min=None, max=None, regex=None, preset=None, choices=None, secret=False)`

Declares an argument.  Built-in presets: `"email"`, `"url"`, `"phone"`, `"uuid"`.

### `@validator(fn)`

Attaches a custom per-command validator called after argument binding.

### `@permission(*perms)`

Requires one or more permission strings on the calling user.

### `@middleware(before=fn, after=fn)`

Attaches command-level middleware.

### `@default_command`

Registers the handler for free-form text input (non-command lines).

---

## CommandParser

```python
from func_parser import CommandParser

p = CommandParser(
    prefix="/",    # command prefix character
    hybrid=True,   # accept both /commands and free text
    debug=False,   # print AST debug info
    dry_run=False, # skip handler execution
)
```

### Methods

| Method | Description |
|--------|-------------|
| `await p.execute(text, ctx)` | Parse and execute a string |
| `p(text, ctx)` | Synchronous wrapper around `execute` |
| `p.help(cmd_name=None)` | Return help string |
| `p.print_help()` | Print help to stdout |
| `p.loop(prompt)` | Sync interactive generator loop |
| `async p.async_loop(prompt)` | Async interactive generator loop |

---

## Parsing Syntax

```
/command arg1 arg2 key=value     → named command
hello world                      → default text handler (hybrid mode)
/a | /b | /c                     → pipeline (output of a → input of b)
/a && /b                         → run b only if a succeeds
/a || /b                         → run b only if a fails
//set x=5                        → set local variable
//setenv HOME=/tmp               → set environment variable
${x} or $VAR                     → variable expansion
/cmd {file.txt}                  → inject file contents as argument
/cmd > out.txt                   → redirect output to file
/cmd >> out.txt                  → append output to file
/cmd >clipboard                  → copy output to clipboard
/execute script.txt              → run a script file line-by-line
# comment                        → ignored
```

---

## Context Object

```python
from func_parser import ExecutionContext, User

ctx = ExecutionContext(
    user=User(id="u1", name="Alice", roles=["admin"]),
    dry_run=False,
    debug=False,
)

# Access inside a handler:
async def my_cmd(ctx, ...):
    ctx.vars          # dict of local variables
    ctx.env           # dict of env variables
    ctx.user          # User object
    ctx.permissions   # list of extra permissions
    ctx.output        # OutputBuffer for streaming
    ctx.set_var(k, v) # set a variable
    ctx.get_var(k)    # look up a variable
    ctx.push_history(entry)  # undo/redo support
    ctx.undo()
    ctx.redo()
```

---

## Middleware

```python
# Global middleware
@p._middleware.before
def log(ctx, cmd_name, args):
    print(f"Running {cmd_name}")
    return args  # can modify args

@p._middleware.after
def audit(ctx, result):
    print(f"Result: {result.status}")
    return result  # can modify result

# Rate limiting
p._middleware.set_rate_limit("expensive_cmd", max_calls=5, window_secs=60.0)
```

---

## Permissions

```python
from func_parser import PermissionChecker

checker = PermissionChecker()
checker.add_role("editor", ["write", "read"])
checker.grant("user_id_42", "publish")
checker.revoke("user_id_42", "publish")
```

Default roles: `admin` (all permissions), `user` (none), `moderator` (moderate).

---

## Scheduler

```python
from func_parser import Scheduler

scheduler = Scheduler(execute_fn=lambda cmd: parser.execute(cmd, ctx))

scheduler.schedule("every 5m", "/refresh")
scheduler.schedule("at 09:00", "/morning_report")

# Cancel all
scheduler.cancel_all()
```

---

## Plugin System

```python
from func_parser import Plugin, PluginManager

class MyPlugin(Plugin):
    name = "my_plugin"

    def register(self, registry):
        from func_parser import CommandInfo
        cmd = CommandInfo(name="plugin_cmd", handler=self.handler)
        registry.register(cmd)

    async def handler(self, ctx):
        return "from plugin"

manager = PluginManager(registry=parser.registry)
manager.load(MyPlugin())
```

---

## I/O Abstraction

```python
from func_parser.io import (
    StdinInputProvider, StdoutOutputHandler,
    FileOutputHandler, ClipboardOutputHandler,
    SimpleCompletionProvider,
)
```

---

## CLI Adapter (prompt_toolkit)

```python
import asyncio
from func_parser.adapters.cli import CLIAdapter

adapter = CLIAdapter(parser, prompt="> ")
asyncio.run(adapter.run())
```

Features: autocompletion, syntax highlighting, live validation, multiline input, history.  
Falls back to basic `input()` if `prompt_toolkit` is not installed.

---

## Examples

| File | What it shows |
|------|---------------|
| `examples/chatbot_example.py` | `@default_command`, variables, multiple commands |
| `examples/cli_example.py` | Pipeline, middleware logging, permissions, CLI demo |
| `examples/scripting_example.py` | `//set`, `${var}`, `/execute`, `&&` / `\|\|`, dry-run, redirect |

Run any example:

```bash
python examples/chatbot_example.py
python examples/cli_example.py
python examples/scripting_example.py
```

---

## Rust Implementation

A companion Rust crate is located in `func_parser_rs/`.  
It provides the same concepts — commands, args, pipeline, context, middleware — via a clean Rust API with macro-based decorators.

```bash
cd func_parser_rs
cargo build
cargo test
cargo run --example basic
```

See `func_parser_rs/README.md` for full documentation.

---

## Running Tests

```bash
pip install pytest pytest-asyncio
pytest
```

---

## License

MIT

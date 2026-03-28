# Task

Build a **modular, extensible command/function parser in Python** designed as a **core engine (not CLI-first)**. Also provide a **Rust implementation** with similar architecture (published to PyPI + Cargo).

---

## Core Principles

* Function-first (CLI = adapter)
* Async-ready
* Extensible via decorators & plugins
* Unified parsing for commands + plain text

---

## Core Architecture

### Command Model

* Command = name + args schema + handler
* Support:

  * positional / named args
  * required / optional
  * defaults
  * variadic args
* Aliases

---

## 🔥 Decorator System (IMPORTANT)

Provide a clean, expressive API:

```python
@command("user.create", aliases=["uc"])
@arg("name", type=str, required=True)
@arg("age", type=int, min=0)
@permission("admin")
async def create_user(ctx, name, age):
    ...
```

Support:

* `@command`
* `@arg`
* `@validator`
* `@permission`
* `@middleware(before=..., after=...)`

Must feel **clean and ergonomic**.

---

## Default Text Command (CRITICAL)

If input is **not a command**, treat it as a call to a default handler:

```python
@default_command
async def text(ctx, content: str):
    ...
```

Example:

```
/voice anna   → command
hello world   → default text command
```

Parser must support both modes:

* strict command parsing
* hybrid (command + free text)

---

## Argument System

* Types: `str`, `int`, `float`, `bool`, custom
* Features:

  * ranges (`1..10`)
  * regex validation
  * presets (email, url, etc.)
  * custom validators
* Interactive args via callback

---

## Parsing Features

### Syntax

* Chaining:

  ```
  cmd1 | cmd2 && cmd3
  ```
* Variables:

  ```
  //set x=5
  ${x}
  ```
* Env:

  ```
  $HOME
  ```

---

## Clipboard Support (NEW)

* Output redirection:

  ```
  cmd > file.txt
  cmd >> file.txt
  cmd >clipboard
  cmd >>clipboard
  ```
* Built-in variable:

  ```
  $clipboard
  ```

---

## File Features (toggleable)

* Argument from file:

  ```
  cmd {file.txt}
  ```
* Execute scripts:

  ```
  /execute script.txt
  ```

---

## Execution Engine

* Async pipeline
* Context object:

  ```python
  ctx.vars
  ctx.env
  ctx.user
  ctx.permissions
  ```
* Streaming output support
* Error system

---

## Control Flow DSL

```
if x > 5:
    cmd
else:
    cmd

while condition():
    cmd
```

* Logical ops: `&& || !`
* Custom condition callbacks

---

## Namespaces

```
user.create
file.read
```

* Grouping + plugins

---

## Permissions

* Roles: admin/user/etc
* Per-command access

---

## Variables

* `//set`, `//setenv`
* `${var}`, `$VAR`
* Scoped

---

## Scheduling

```
every 5m: cmd
at 12:00: cmd
```

---

## I/O Abstraction

```python
input_provider()
output_handler()
completion_provider()
```

---

## CLI Adapter

Build CLI using prompt_toolkit with:

* autocompletion
* syntax highlighting
* multiline input
* live validation
* restricted chars
* password args
* history

⚠️ Must be adapter only, not core logic.

---

## Extensibility

* Plugin system
* Middleware:

  ```python
  before_execute(ctx)
  after_execute(ctx)
  ```

---

## Extra Features

* Auto help from type hints
* AST debug mode
* Dry-run mode
* Undo/redo
* Rate limiting
* Localization

---

## Rust Version (IMPORTANT)

Create equivalent project in Rust:

* Same concepts (commands, args, pipeline, context)
* Macro-based decorators (proc macros):

  ```rust
  #[command(name = "user.create")]
  async fn create_user(...) {}
  ```
* Publish:

  * Python version → PyPI
  * Rust version → Cargo
* Optional: Python bindings via `pyo3`

---

## Deliverables

* Python core engine
* Rust core engine
* CLI adapter
* Examples:

  * chatbot
  * CLI
  * scripting

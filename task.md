# Task

IMPORTANT:
- Do NOT ask questions. All behavior is fully specified here.
- If something is not explicitly defined, choose the most strict and predictable behavior and document it in progress.md.
- Do NOT modify semantics of existing tests unless explicitly required by this document.
- Do NOT modify build artifacts (target/, __pycache__, etc).
- Follow idiomatic Rust and Python, but keep feature parity.

---

## Progress Tracking
On completing each task, mark it as done.
If interrupted, continue from progress.md.

---

## 1. Python + UV
( ) Make Python project runnable with UV.

Requirements:
- `uv run` must run the project
- `uv run pytest` must pass all tests
- Do NOT restructure project unless required
- Examples may be moved inside the package if needed

---

## 2. Built-in help and exit commands

( ) Implement built-in help and exit commands (Python + Rust)

Rules:
- They are NOT created via decorators/macros
- Controlled via parser initializer flags:
  - enable_help (default: true)
  - enable_exit (default: true)

Defaults:
- help command: `/help`
- exit command: `/exit and /quit`

Customization:
- parser.set_help_aliases([...])
- parser.set_exit_aliases([...])
- @parser.exit_cleanup() decorator for cleanup functions

Behavior:
- Ctrl+C:
  - if exit enabled → executes exit command (with cleanup)
  - if disabled → raises interrupt (SystemExit / panic depending on context)

---

## 3. "+" single-letter alias system

( ) Implement "+" alias system (Python + Rust)

Rules:
- "+" marks the next character as a single-letter alias
- "+" is REMOVED from final command/alias

Examples:
- "+help" → `/help` + `/h`
- "e+xit" → `/exit` + `/x`
- "+he+lp" → `/help` + `/h` + `/l`
- aliases=["+quit"] → `/quit` + `/q`

Applies to:
- command names
- aliases

Validation:
- character after "+" MUST be [a-zA-Z]
- otherwise:
  - Python → raise exception
  - Rust → compile error (if macro) or panic (runtime)

Duplicates:
- ANY duplicate command or alias MUST fail:
  - Python → exception at registration
  - Rust:
    - macro → compile error
    - runtime → panic

---

## 4. Help from docstrings / doc comments

( ) Implement doc-based help

Python:
- Use `docstring-parser`
- Support: Google, NumPy, ReST, Epydoc
- Extract:
  - function description → command help
  - argument descriptions → argument help

Rust:
- Use `///` doc comments
- Behavior similar to clap:
  - comment before command → command help
  - comment before argument → argument help

If docstring missing:
- fallback to explicit help= or empty

---

## 5. Types, unions, traits, arrays, matrices

( ) Implement advanced type system

### Union types
- Support multiple types:
  - Python: `int | float`
  - Rust: equivalent enum/trait handling

### Traits (pseudo-traits)
- Defined like:
  - trait=traits.addable
  - trait=traits.comparable

Traits mean:
- value must support required operations

Minimum required traits:
- addable
- subtractable
- comparable

### Arrays
- Syntax:
  - Python: list[...] or array[...] equivalent
  - Rust: Vec<...>

### Matrices
- JSON-like input:
  - `[ [1,2], [3,4] ]`

### JSON support
- Unified JSON parsing:
  - arrays
  - matrices
  - objects

Rust:
- MUST use serde_json

---

## 6. Context expirable values (CTX)

( ) Implement expirable variables

Storage:
- inside ctx.vars

Each variable:
- value
- optional expiration:
  - TTL (seconds)
  - or datetime

Syntax:
- `$var` → value
- `$var!` → remaining TTL (seconds)

Rules:
- if no expiration:
  - `$var!` returns -1

Cleanup:
- happens on access ONLY (lazy cleanup)
- no background tasks

---

## 7. CLI loop and execution

( ) Implement CLI execution (Python + Rust)

### parser.run()
- blocking CLI loop
- reads stdin
- executes commands

Behavior:
- Ctrl+C:
  - if exit enabled → run exit command
  - else → raise interrupt

### parser.loop()
- generator / iterator
- yields command results
- allows manual control

### exit_no_interrupt()
- disables Ctrl+C interruption handling
- gives full control to user

---

## 8. Tests and examples

( ) Update ALL tests and examples

Rules:
- MUST cover:
  - "+" aliases
  - docstring help
  - traits
  - arrays/matrices
  - expirable vars
  - CLI loop

- DO NOT weaken assertions
- DO NOT remove tests unless invalid

---

## 9. Rust examples

( ) Add Rust examples

Required:
- one example per feature
- complex example combining:
  - traits
  - arrays
  - context vars
  - CLI loop

---

## 10. .gitignore and cleanup

( ) Fix repository hygiene

Requirements:
- remove tracked build artifacts
- add proper .gitignore

Must ignore:
- target/
- __pycache__/
- *.pyc
- .pytest_cache/
- .mypy_cache/
- venv/
- .venv/

IMPORTANT:
- agent MUST NOT read or diff ignored files
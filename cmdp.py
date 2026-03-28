import shlex
import inspect
from typing import Any, Callable, Dict, List, Optional, Generator
from dataclasses import dataclass, field

@dataclass
class CommandArgument:
    name: str
    arg_type: type = str
    default: Any = None
    doc: str = ""

    def __str__(self):
        return f"<{self.name}:{self.arg_type.__name__}>" if self.default is None else f"[{self.name}]"

@dataclass
class CommandResult:
    name: str
    args: Dict[str, Any]
    is_event: bool
    status: str
    output: Any = None  # Stores the return value of the function

class CommandParser:
    def __init__(self, default_fn: Optional[Callable] = None):
        self.commands: Dict[str, Dict] = {}
        self.default_fn = default_fn

    def command(self, name: str, is_event: bool = False, doc: str = ""):
        """Decorator to start a command definition."""
        def decorator(fn: Callable):
            if name not in self.commands:
                self.commands[name] = {'args': [], 'fn': fn, 'is_event': is_event, 'doc': doc}
            else:
                self.commands[name]['fn'] = fn
                self.commands[name]['is_event'] = is_event
                self.commands[name]['doc'] = doc or fn.__doc__ or ""
            return fn
        return decorator

    def argument(self, cmd_name: str, name: str, arg_type: type = str, default: Any = None, doc: str = ""):
        """Decorator/Method to add arguments to a specific command."""
        arg = CommandArgument(name, arg_type, default, doc)
        if cmd_name not in self.commands:
            self.commands[cmd_name] = {'args': [arg], 'fn': None, 'is_event': False, 'doc': ""}
        else:
            self.commands[cmd_name]['args'].append(arg)
        
        def decorator(fn: Callable):
            return fn
        return decorator

    def print_help(self, cmd_name: Optional[str] = None):
        if cmd_name and cmd_name in self.commands:
            c = self.commands[cmd_name]
            args_str = " ".join(str(a) for a in c['args'])
            print(f"Usage: /{cmd_name} {args_str}")
            if c['doc']: print(f"Description: {c['doc']}")
        else:
            print("\n--- Available Commands ---")
            for name, info in self.commands.items():
                print(f" /{name:<10} {info['doc']}")

    def __call__(self, input_str: str) -> CommandResult:
        """The magic 'execute or return event' method."""
        if not input_str.startswith('/'):
            # Default behavior: No slash? Send the whole string to default_fn
            val = self.default_fn(input_str) if self.default_fn else None
            return CommandResult("default", {"text": input_str}, False, "no_command", val)

        try:
            parts = shlex.split(input_str[1:])
        except ValueError:
            return CommandResult("error", {}, False, "malformed_quotes")

        if not parts:
            return CommandResult("none", {}, False, "no_command")

        cmd_name = parts[0]
        if cmd_name == "help":
            self.print_help()
            return CommandResult("help", {}, False, "success")

        if cmd_name not in self.commands:
            print(f"Unknown command: /{cmd_name}. Type /help for list.")
            return CommandResult(cmd_name, {}, False, "unknown")

        cmd_info = self.commands[cmd_name]
        raw_args = parts[1:]
        parsed_args = {}

        # Parse arguments with type safety
        for i, arg_meta in enumerate(cmd_info['args']):
            if i < len(raw_args):
                try:
                    parsed_args[arg_meta.name] = arg_meta.arg_type(raw_args[i])
                except (ValueError, TypeError):
                    print(f"Error: Argument '{arg_meta.name}' must be {arg_meta.arg_type.__name__}")
                    self.print_help(cmd_name)
                    return CommandResult(cmd_name, {}, False, "invalid_args")
            elif arg_meta.default is not None:
                parsed_args[arg_meta.name] = arg_meta.default
            else:
                print(f"Error: Missing required argument '{arg_meta.name}'")
                self.print_help(cmd_name)
                return CommandResult(cmd_name, {}, False, "missing_args")

        # Logic: If it's a function call, do it. If it's an event, just return state.
        execution_result = None
        if not cmd_info['is_event'] and cmd_info['fn']:
            execution_result = cmd_info['fn'](**parsed_args)

        return CommandResult(
            name=cmd_name,
            args=parsed_args,
            is_event=cmd_info['is_event'],
            status="success",
            output=execution_result
        )

    def loop(self, prompt: str = "> ") -> Generator[CommandResult, None, None]:
        """Generator that yields results infinitely."""
        while True:
            try:
                line = input(prompt)
                yield self(line)
            except EOFError:
                break
            except KeyboardInterrupt:
                print("\nInterrupt received. Exiting...")
                break
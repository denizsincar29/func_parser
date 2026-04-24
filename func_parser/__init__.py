"""func_parser — modular, extensible command/function parser."""
from .core.models import ArgDef, CommandInfo, CommandResult, OutputRedirect, ArgKind
from .core.errors import (
    FuncParserError, ParseError, CommandNotFoundError, MissingArgError,
    InvalidArgError, ValidationError, PermissionDeniedError, SchedulerError,
    MiddlewareError, RateLimitError,
)
from .core.context import ExecutionContext, User, OutputBuffer
from .core.variables import VariableStore
from .core.permissions import PermissionChecker
from .core.registry import CommandRegistry
from .core.middleware import MiddlewareChain
from .core.pipeline import AsyncPipeline
from .decorators import (
    CommandParser,
    command, arg, validator, permission, middleware, default_command,
    get_default_registry, get_default_parser,
)
from .plugins.base import Plugin, PluginManager
from .scheduler import Scheduler
from .io import (
    InputProvider, OutputHandler, CompletionProvider,
    StdinInputProvider, StdoutOutputHandler, FileOutputHandler,
    ClipboardOutputHandler, SimpleCompletionProvider,
)

__version__ = "0.1.0"
__all__ = [
    # models
    "ArgDef", "CommandInfo", "CommandResult", "OutputRedirect", "ArgKind",
    # errors
    "FuncParserError", "ParseError", "CommandNotFoundError", "MissingArgError",
    "InvalidArgError", "ValidationError", "PermissionDeniedError", "SchedulerError",
    "MiddlewareError", "RateLimitError",
    # context
    "ExecutionContext", "User", "OutputBuffer",
    # variables
    "VariableStore",
    # permissions
    "PermissionChecker",
    # registry
    "CommandRegistry",
    # middleware
    "MiddlewareChain",
    # pipeline
    "AsyncPipeline",
    # decorators
    "CommandParser",
    "command", "arg", "validator", "permission", "middleware", "default_command",
    "get_default_registry", "get_default_parser",
    # plugins
    "Plugin", "PluginManager",
    # scheduler
    "Scheduler",
    # io
    "InputProvider", "OutputHandler", "CompletionProvider",
    "StdinInputProvider", "StdoutOutputHandler", "FileOutputHandler",
    "ClipboardOutputHandler", "SimpleCompletionProvider",
    # version
    "__version__",
]

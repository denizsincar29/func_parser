"""Error classes for func_parser."""

__all__ = [
    "FuncParserError", "ParseError", "CommandNotFoundError", "MissingArgError",
    "InvalidArgError", "ValidationError", "PermissionDeniedError",
    "SchedulerError", "MiddlewareError", "RateLimitError",
]


class FuncParserError(Exception):
    """Base class for all func_parser errors."""
    pass


class ParseError(FuncParserError):
    """Error during parsing."""
    pass


class CommandNotFoundError(FuncParserError):
    """Raised when a command is not found in the registry."""

    def __init__(self, name: str):
        self.command_name = name
        super().__init__(f"Command not found: {name!r}")


class MissingArgError(FuncParserError):
    """Raised when a required argument is not provided."""

    def __init__(self, arg_name: str, cmd_name: str = ""):
        self.arg_name = arg_name
        self.command_name = cmd_name
        msg = f"Missing required argument: {arg_name!r}"
        if cmd_name:
            msg += f" for command {cmd_name!r}"
        super().__init__(msg)


class InvalidArgError(FuncParserError):
    """Raised when an argument has an invalid value."""

    def __init__(self, arg_name: str, reason: str = ""):
        self.arg_name = arg_name
        super().__init__(f"Invalid argument {arg_name!r}: {reason}")


class ValidationError(FuncParserError):
    """Raised when a validator rejects an argument value."""

    def __init__(self, arg_name: str, message: str):
        self.arg_name = arg_name
        super().__init__(f"Validation failed for {arg_name!r}: {message}")


class PermissionDeniedError(FuncParserError):
    """Raised when a user lacks the required permission."""

    def __init__(self, permission: str, user: str = ""):
        self.permission = permission
        msg = f"Permission denied: {permission!r}"
        if user:
            msg += f" for user {user!r}"
        super().__init__(msg)


class SchedulerError(FuncParserError):
    """Error in the task scheduler."""
    pass


class MiddlewareError(FuncParserError):
    """Error raised by middleware."""
    pass


class RateLimitError(FuncParserError):
    """Raised when a command's rate limit is exceeded."""

    def __init__(self, cmd_name: str):
        super().__init__(f"Rate limit exceeded for command: {cmd_name!r}")

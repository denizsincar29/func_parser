"""Argument coercion and validation logic."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from .errors import InvalidArgError, ValidationError
from .models import ArgDef

__all__ = ["PRESETS", "coerce_type", "validate_arg"]

PRESETS: Dict[str, str] = {
    "email": r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
    "url": r"^https?://[^\s/$.?#].[^\s]*$",
    "phone": r"^\+?[\d\s\-().]{7,20}$",
    "uuid": r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
}

_BOOL_TRUE = {"true", "yes", "1", "on"}
_BOOL_FALSE = {"false", "no", "0", "off"}


def coerce_type(value: str, arg_def: ArgDef) -> Any:
    """Convert *value* (a raw string) to the type declared in *arg_def*.

    Raises :class:`InvalidArgError` on failure.
    """
    target = arg_def.type
    if target is bool:
        low = value.lower()
        if low in _BOOL_TRUE:
            return True
        if low in _BOOL_FALSE:
            return False
        raise InvalidArgError(
            arg_def.name,
            f"expected bool (true/false/yes/no/1/0), got {value!r}",
        )
    try:
        return target(value)
    except (ValueError, TypeError) as exc:
        raise InvalidArgError(
            arg_def.name,
            f"cannot convert {value!r} to {target.__name__}: {exc}",
        ) from exc


def validate_arg(name: str, value: Any, arg_def: ArgDef) -> Any:
    """Run all configured validations on *value*.

    Returns the (possibly unchanged) value, or raises an appropriate error.
    """
    # choices
    if arg_def.choices is not None and value not in arg_def.choices:
        raise InvalidArgError(
            name,
            f"must be one of {arg_def.choices!r}, got {value!r}",
        )

    # numeric range
    if arg_def.min is not None:
        try:
            if float(value) < arg_def.min:
                raise InvalidArgError(name, f"must be >= {arg_def.min}, got {value!r}")
        except (TypeError, ValueError):
            pass  # non-numeric — skip range check

    if arg_def.max is not None:
        try:
            if float(value) > arg_def.max:
                raise InvalidArgError(name, f"must be <= {arg_def.max}, got {value!r}")
        except (TypeError, ValueError):
            pass

    # regex
    pattern: Optional[str] = arg_def.regex
    if arg_def.preset and arg_def.preset in PRESETS:
        pattern = PRESETS[arg_def.preset]

    if pattern is not None:
        if not re.match(pattern, str(value)):
            label = f"preset {arg_def.preset!r}" if arg_def.preset else "regex"
            raise ValidationError(name, f"value {value!r} does not match {label} pattern")

    # custom validators
    for v_fn in arg_def.validators:
        result = v_fn(value)
        if result is False:
            raise ValidationError(name, f"custom validator {v_fn.__name__!r} rejected {value!r}")
        if isinstance(result, str):
            raise ValidationError(name, result)

    return value

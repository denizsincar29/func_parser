"""Scoped variable store for func_parser."""
from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional

__all__ = ["VariableStore"]


class VariableStore:
    """Scoped variable store supporting ``//set``, ``//setenv``, ``${var}``, ``$VAR``."""

    def __init__(self, parent: Optional["VariableStore"] = None) -> None:
        self._local: Dict[str, Any] = {}
        self._env: Dict[str, str] = {}
        self.parent = parent

    def set(self, name: str, value: Any, scope: str = "local") -> None:
        """Set a variable.  *scope* is ``"local"`` or ``"env"``."""
        if scope == "env":
            self._env[name] = str(value)
            os.environ[name] = str(value)
        else:
            self._local[name] = value

    def get(self, name: str, default: Any = None) -> Any:
        """Resolve a variable, walking up the scope chain."""
        if name in self._local:
            return self._local[name]
        if name in self._env:
            return self._env[name]
        env_val = os.environ.get(name)
        if env_val is not None:
            return env_val
        if self.parent:
            return self.parent.get(name, default)
        return default

    def expand(self, text: str) -> str:
        """Expand ``${var}`` and ``$VAR`` placeholders in *text*."""
        def replace(m: re.Match) -> str:
            key = m.group(1) or m.group(2)
            val = self.get(key)
            return str(val) if val is not None else m.group(0)

        text = re.sub(r'\$\{([^}]+)\}', replace, text)
        text = re.sub(r'\$([A-Za-z_][A-Za-z0-9_]*)', replace, text)
        return text

    def child(self) -> "VariableStore":
        """Create a child scope that inherits from this store."""
        return VariableStore(parent=self)

    def all_vars(self) -> Dict[str, Any]:
        """Return all variables visible from this scope."""
        result: Dict[str, Any] = {}
        if self.parent:
            result.update(self.parent.all_vars())
        result.update(self._env)
        result.update(self._local)
        return result

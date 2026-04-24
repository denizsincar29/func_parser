"""Base plugin classes for func_parser."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.registry import CommandRegistry

__all__ = ["Plugin", "PluginManager"]


class Plugin(ABC):
    """Base class for func_parser plugins."""

    name: str = "unnamed_plugin"
    version: str = "0.0.1"
    description: str = ""

    @abstractmethod
    def register(self, registry: "CommandRegistry") -> None:
        """Register commands/middleware provided by this plugin."""
        ...

    def on_load(self) -> None:
        """Called when the plugin is loaded."""
        pass

    def on_unload(self) -> None:
        """Called when the plugin is unloaded."""
        pass


class PluginManager:
    """Manages loading and unloading of :class:`Plugin` instances."""

    def __init__(self, registry: "CommandRegistry") -> None:
        self._registry = registry
        self._plugins: List[Plugin] = []

    def load(self, plugin: Plugin) -> None:
        """Load and register *plugin*."""
        plugin.on_load()
        plugin.register(self._registry)
        self._plugins.append(plugin)

    def unload(self, plugin_name: str) -> None:
        """Unload the plugin named *plugin_name*."""
        for p in list(self._plugins):
            if p.name == plugin_name:
                p.on_unload()
                self._plugins.remove(p)
                return

    @property
    def loaded(self) -> List[str]:
        """Names of all currently loaded plugins."""
        return [p.name for p in self._plugins]

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import threading
from importlib.metadata import entry_points
from typing import Any

import pluggy
from typing_extensions import Self

from aiperf import AIPERF_PROJECT_NAME
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.base_enums import CaseInsensitiveStrEnum
from aiperf.common.hookspecs import AIPerfHookSpecs
from aiperf.common.mixins.aiperf_logger_mixin import AIPerfLoggerMixin
from aiperf.common.plugin_metadata import AIPerfPluginMetadata
from aiperf.common.protocols import AIPerfUIProtocol


class AIPerfPluginType(CaseInsensitiveStrEnum):
    UI = "aiperf.ui"


class PluginNotFoundError(RuntimeError):
    """Exception raised when a plugin is not found."""

    def __init__(self, plugin_type: AIPerfPluginType, name: str) -> None:
        super().__init__(f"class not found: {plugin_type}:{name}")


class PluginFactory(AIPerfLoggerMixin):
    """Factory for registering and creating plugins."""

    _instance_lock: threading.Lock = threading.Lock()

    def __new__(cls) -> Self:
        """Create a new plugin factory."""
        if not hasattr(cls, "_instance"):
            with cls._instance_lock:
                if not hasattr(cls, "_instance"):
                    cls._instance = super().__new__(cls)
                    cls._instance._init_singleton()
        return cls._instance

    def _init_singleton(self) -> None:
        """Initialize the plugin factory singleton."""
        self.pm = pluggy.PluginManager(AIPERF_PROJECT_NAME)
        self.pm.add_hookspecs(AIPerfHookSpecs)
        self._plugin_classes: dict[AIPerfPluginType, dict[str, type[Any]]] = {
            plugin_type: {} for plugin_type in AIPerfPluginType
        }
        self._register_all()

    def _register_all(self) -> None:
        """Register all plugins."""
        for plugin_type in AIPerfPluginType:
            for ep in entry_points(group=str(plugin_type)):
                factory_func: Any = ep.load()
                plugin_cls: type[Any] = factory_func()
                name: str = plugin_cls.get_metadata().name
                self._plugin_classes[plugin_type][name] = plugin_cls
                self.pm.register(plugin_cls, name=f"{plugin_type}:{name}")

    def list_plugins(self, plugin_type: AIPerfPluginType) -> list[str]:
        """List all plugins of the given plugin type."""
        return list(self._plugin_classes[plugin_type].keys())

    def get_metadata(
        self, plugin_type: AIPerfPluginType, name: str
    ) -> AIPerfPluginMetadata:
        """Get the metadata for the given plugin type and name."""
        cls = self._get_plugin_class_internal(plugin_type=plugin_type, name=name)
        return cls.get_metadata()

    def _create_instance_internal(
        self, plugin_type: AIPerfPluginType, name: str, **kwargs: Any
    ) -> Any:
        """Internal method to create a new instance of the given plugin type and name."""
        cls = self._get_plugin_class_internal(plugin_type=plugin_type, name=name)
        return cls(**kwargs)

    def _get_plugin_class_internal(
        self, plugin_type: AIPerfPluginType, name: str
    ) -> type[Any]:
        """Internal method to get the plugin class for the given plugin type and name."""
        cls = self._plugin_classes[plugin_type].get(name)
        if self.is_trace_enabled:
            self.trace(
                f"Getting plugin class '{name}' for plugin type '{plugin_type}'."
            )
        if not cls:
            self.error(
                f"Plugin class '{name}' not found for plugin type '{plugin_type}'."
            )
            raise PluginNotFoundError(plugin_type=plugin_type, name=name)
        if self.is_trace_enabled:
            self.trace(
                f"Plugin class '{name}' found for plugin type '{plugin_type}': {cls!r}."
            )
        return cls

    def create_ui(
        self, name: str, service_config: ServiceConfig, user_config: UserConfig
    ) -> AIPerfUIProtocol:
        """Create a new UI instance based on the given name."""
        return self._create_instance_internal(
            plugin_type=AIPerfPluginType.UI,
            name=name,
            service_config=service_config,
            user_config=user_config,
        )

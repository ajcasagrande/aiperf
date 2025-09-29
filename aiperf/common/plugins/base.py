# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Base classes and decorators for request converter plugins."""

from abc import ABC, abstractmethod
from typing import Any

import pluggy

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.enums import EndpointType
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.models import Turn

from .hookspecs import PROJECT_NAME

# Create the hookimpl marker for implementing hooks
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class BaseRequestConverterPlugin(AIPerfLoggerMixin, ABC):
    """Base class for request converter plugins."""

    def __init__(self) -> None:
        """Initialize the plugin."""
        super().__init__()

    @hookimpl
    def get_plugin_name(self) -> str:
        """Return the name of this plugin."""
        return self.__class__.__name__

    @hookimpl
    def get_plugin_priority(self) -> int:
        """Return the priority of this plugin."""
        return 0  # Default priority

    @hookimpl
    @abstractmethod
    def get_supported_endpoint_types(self) -> list[EndpointType]:
        """Return the list of endpoint types this plugin supports."""

    @hookimpl
    def can_handle_endpoint_type(self, endpoint_type: EndpointType) -> bool:
        """Check if this plugin can handle the specified endpoint type."""
        return endpoint_type in self.get_supported_endpoint_types()

    @hookimpl
    @abstractmethod
    async def format_payload(
        self,
        endpoint_type: EndpointType,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any] | None:
        """Format a payload for the specified endpoint type."""


def request_converter_plugin(
    endpoint_types: list[EndpointType] | EndpointType,
    name: str | None = None,
    priority: int = 0,
    auto_register: bool = True,
):
    """Decorator for creating request converter plugins.

    Args:
        endpoint_types: Single endpoint type or list of endpoint types this plugin supports.
        name: Optional custom name for the plugin. If None, uses class name.
        priority: Priority of the plugin (higher = more preferred).
        auto_register: Whether to automatically register the plugin with the global manager.
    """
    if isinstance(endpoint_types, EndpointType):
        endpoint_types = [endpoint_types]

    def decorator(cls):
        # Add hook implementations to the class
        original_init = cls.__init__

        def __init__(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            if hasattr(super(cls, self), "__init__"):
                super(cls, self).__init__()

        cls.__init__ = __init__

        # Add hook implementations
        @hookimpl
        def get_plugin_name(self) -> str:
            return name if name is not None else cls.__name__

        @hookimpl
        def get_plugin_priority(self) -> int:
            return priority

        @hookimpl
        def get_supported_endpoint_types(self) -> list[EndpointType]:
            return endpoint_types

        @hookimpl
        def can_handle_endpoint_type(self, endpoint_type: EndpointType) -> bool:
            return endpoint_type in endpoint_types

        # Add methods to class
        cls.get_plugin_name = get_plugin_name
        cls.get_plugin_priority = get_plugin_priority
        cls.get_supported_endpoint_types = get_supported_endpoint_types
        cls.can_handle_endpoint_type = can_handle_endpoint_type

        # Auto-register if requested
        if auto_register:
            # Register the plugin class with the manager
            # This will be done when the manager discovers plugins
            cls._aiperf_plugin_auto_register = True
            cls._aiperf_plugin_endpoint_types = endpoint_types
            cls._aiperf_plugin_name = name
            cls._aiperf_plugin_priority = priority

        return cls

    return decorator


def register_plugin_class(plugin_class: type) -> None:
    """Manually register a plugin class with the global manager.

    Args:
        plugin_class: The plugin class to register.
    """
    from .manager import get_plugin_manager

    manager = get_plugin_manager()
    manager.register_plugin_class(plugin_class)


def register_plugin_instance(plugin_instance: Any) -> None:
    """Manually register a plugin instance with the global manager.

    Args:
        plugin_instance: The plugin instance to register.
    """
    from .manager import get_plugin_manager

    manager = get_plugin_manager()
    manager.register_plugin(plugin_instance)

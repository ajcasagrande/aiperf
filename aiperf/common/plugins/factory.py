# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Pluggy-based factory for request converters."""

from typing import Any

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.enums import EndpointType
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.models import Turn
from aiperf.common.protocols import RequestConverterProtocol

from .manager import get_plugin_manager


class PluggyRequestConverterAdapter(AIPerfLoggerMixin):
    """Adapter that makes a pluggy plugin compatible with RequestConverterProtocol."""

    def __init__(self, endpoint_type: EndpointType):
        """Initialize the adapter.

        Args:
            endpoint_type: The endpoint type this adapter handles.
        """
        super().__init__()
        self.endpoint_type = endpoint_type
        self.plugin_manager = get_plugin_manager()

    async def format_payload(
        self, model_endpoint: ModelEndpointInfo, turn: Turn
    ) -> dict[str, Any]:
        """Format payload using the pluggy system.

        Args:
            model_endpoint: Information about the model endpoint.
            turn: The turn data to format.

        Returns:
            Formatted payload dictionary.
        """
        return await self.plugin_manager.format_payload(
            self.endpoint_type, model_endpoint, turn
        )


class PluggyRequestConverterFactory(AIPerfLoggerMixin):
    """Factory that creates RequestConverterProtocol instances using pluggy plugins."""

    def __init__(self):
        """Initialize the factory."""
        super().__init__()
        self.plugin_manager = get_plugin_manager()

    def create_instance(self, endpoint_type: EndpointType) -> RequestConverterProtocol:
        """Create a request converter instance for the given endpoint type.

        Args:
            endpoint_type: The endpoint type to create a converter for.

        Returns:
            A RequestConverterProtocol instance.
        """
        return PluggyRequestConverterAdapter(endpoint_type)

    def can_handle_endpoint_type(self, endpoint_type: EndpointType) -> bool:
        """Check if the pluggy system can handle the given endpoint type.

        Args:
            endpoint_type: The endpoint type to check.

        Returns:
            True if a plugin can handle the endpoint type, False otherwise.
        """
        try:
            self.plugin_manager.get_plugin_for_endpoint_type(endpoint_type)
            return True
        except Exception:
            return False

    def list_supported_endpoint_types(self) -> list[EndpointType]:
        """List all endpoint types supported by registered plugins.

        Returns:
            List of supported EndpointType values.
        """
        supported_types = set()
        plugins_info = self.plugin_manager.list_plugins()

        for _, endpoint_types in plugins_info:
            supported_types.update(endpoint_types)

        return list(supported_types)

    def get_plugin_info(self) -> list[tuple[str, list[EndpointType]]]:
        """Get information about all registered plugins.

        Returns:
            List of tuples containing (plugin_name, supported_endpoint_types).
        """
        return self.plugin_manager.list_plugins()


# Global factory instance
_pluggy_factory: PluggyRequestConverterFactory | None = None


def get_pluggy_factory() -> PluggyRequestConverterFactory:
    """Get the global pluggy factory instance.

    Returns:
        The global PluggyRequestConverterFactory instance.
    """
    global _pluggy_factory
    if _pluggy_factory is None:
        _pluggy_factory = PluggyRequestConverterFactory()
    return _pluggy_factory

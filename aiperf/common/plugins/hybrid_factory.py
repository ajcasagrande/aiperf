# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Hybrid factory that can use both traditional factories and pluggy plugins."""

from typing import Any

from aiperf.common.enums import EndpointType
from aiperf.common.exceptions import AIPerfError
from aiperf.common.factories import (
    RequestConverterFactory as OriginalRequestConverterFactory,
)
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.protocols import RequestConverterProtocol

from .factory import get_pluggy_factory
from .manager import PluginNotFoundError


class HybridRequestConverterFactory(AIPerfLoggerMixin):
    """Factory that tries pluggy first, then falls back to the original factory system."""

    def __init__(self, prefer_pluggy: bool = True):
        """Initialize the hybrid factory.

        Args:
            prefer_pluggy: If True, try pluggy first. If False, try original factory first.
        """
        super().__init__()
        self.prefer_pluggy = prefer_pluggy
        self.pluggy_factory = get_pluggy_factory()

    def create_instance(self, endpoint_type: EndpointType) -> RequestConverterProtocol:
        """Create a request converter instance for the given endpoint type.

        Args:
            endpoint_type: The endpoint type to create a converter for.

        Returns:
            A RequestConverterProtocol instance.

        Raises:
            AIPerfError: If no converter can be found for the endpoint type.
        """
        if self.prefer_pluggy:
            # Try pluggy first
            try:
                if self.pluggy_factory.can_handle_endpoint_type(endpoint_type):
                    self.debug(
                        f"Using pluggy plugin for endpoint type: {endpoint_type}"
                    )
                    return self.pluggy_factory.create_instance(endpoint_type)
            except (PluginNotFoundError, Exception) as e:
                self.debug(f"Pluggy failed for {endpoint_type}: {e}")

            # Fall back to original factory
            try:
                self.debug(
                    f"Falling back to original factory for endpoint type: {endpoint_type}"
                )
                return OriginalRequestConverterFactory.create_instance(endpoint_type)
            except Exception as e:
                self.debug(f"Original factory failed for {endpoint_type}: {e}")
        else:
            # Try original factory first
            try:
                self.debug(f"Using original factory for endpoint type: {endpoint_type}")
                return OriginalRequestConverterFactory.create_instance(endpoint_type)
            except Exception as e:
                self.debug(f"Original factory failed for {endpoint_type}: {e}")

            # Fall back to pluggy
            try:
                if self.pluggy_factory.can_handle_endpoint_type(endpoint_type):
                    self.debug(
                        f"Falling back to pluggy for endpoint type: {endpoint_type}"
                    )
                    return self.pluggy_factory.create_instance(endpoint_type)
            except (PluginNotFoundError, Exception) as e:
                self.debug(f"Pluggy failed for {endpoint_type}: {e}")

        raise AIPerfError(
            f"No request converter found for endpoint type: {endpoint_type}. "
            f"Tried both pluggy plugins and original factory."
        )

    def list_all_supported_types(self) -> dict[str, list[EndpointType]]:
        """List all supported endpoint types from both systems.

        Returns:
            Dictionary with 'pluggy' and 'original' keys containing lists of supported types.
        """
        result = {"pluggy": [], "original": []}

        # Get pluggy supported types
        try:
            result["pluggy"] = self.pluggy_factory.list_supported_endpoint_types()
        except Exception as e:
            self.warning(f"Error getting pluggy supported types: {e}")

        # Get original factory supported types
        try:
            original_classes = (
                OriginalRequestConverterFactory.get_all_classes_and_types()
            )
            result["original"] = [
                endpoint_type for _, endpoint_type in original_classes
            ]
        except Exception as e:
            self.warning(f"Error getting original factory supported types: {e}")

        return result

    def get_detailed_info(self) -> dict[str, Any]:
        """Get detailed information about both plugin systems.

        Returns:
            Dictionary containing detailed information about both systems.
        """
        info = {
            "pluggy_plugins": [],
            "original_classes": [],
            "supported_types": self.list_all_supported_types(),
        }

        # Get pluggy plugin info
        try:
            info["pluggy_plugins"] = self.pluggy_factory.get_plugin_info()
        except Exception as e:
            self.warning(f"Error getting pluggy plugin info: {e}")

        # Get original factory info
        try:
            info["original_classes"] = (
                OriginalRequestConverterFactory.get_all_classes_and_types()
            )
        except Exception as e:
            self.warning(f"Error getting original factory info: {e}")

        return info


# Global hybrid factory instance
_hybrid_factory: HybridRequestConverterFactory | None = None


def get_hybrid_factory(prefer_pluggy: bool = True) -> HybridRequestConverterFactory:
    """Get the global hybrid factory instance.

    Args:
        prefer_pluggy: If True, prefer pluggy plugins over original factory.

    Returns:
        The global HybridRequestConverterFactory instance.
    """
    global _hybrid_factory
    if _hybrid_factory is None:
        _hybrid_factory = HybridRequestConverterFactory(prefer_pluggy=prefer_pluggy)
    return _hybrid_factory

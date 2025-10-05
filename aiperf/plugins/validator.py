# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Plugin Validator (AIP-001)

Validates plugins conform to their respective protocols.
Ensures type safety and contract compliance.
"""

import inspect
from typing import Any, TYPE_CHECKING, get_origin, get_args, Union

from aiperf.common.aiperf_logger import AIPerfLogger

if TYPE_CHECKING:
    from aiperf.plugins.protocols import (
        PluginMetadataProtocol,
        MetricPluginProtocol,
        EndpointPluginProtocol,
        DataExporterPluginProtocol,
        TransportPluginProtocol,
        ProcessorPluginProtocol,
        CollectorPluginProtocol,
    )

logger = AIPerfLogger(__name__)


# Lazy load protocols to avoid circular imports
_PROTOCOL_MAP = None

def _get_protocol_map():
    """Lazy load protocol map to avoid circular imports."""
    global _PROTOCOL_MAP
    if _PROTOCOL_MAP is None:
        from aiperf.plugins.protocols import (
            MetricPluginProtocol,
            EndpointPluginProtocol,
            DataExporterPluginProtocol,
            TransportPluginProtocol,
            ProcessorPluginProtocol,
            CollectorPluginProtocol,
        )
        _PROTOCOL_MAP = {
            "aiperf.metric": MetricPluginProtocol,
            "aiperf.endpoint": EndpointPluginProtocol,
            "aiperf.data_exporter": DataExporterPluginProtocol,
            "aiperf.transport": TransportPluginProtocol,
            "aiperf.processor": ProcessorPluginProtocol,
            "aiperf.collector": CollectorPluginProtocol,
        }
    return _PROTOCOL_MAP


# Public API for accessing protocol map
def get_protocol_map():
    """Get the protocol map (public API for tests)."""
    return _get_protocol_map()


# Module-level __getattr__ to support lazy loading of PROTOCOL_MAP
def __getattr__(name):
    """Support lazy loading of PROTOCOL_MAP."""
    if name == 'PROTOCOL_MAP':
        return _get_protocol_map()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


class PluginValidator:
    """
    Validates plugins against their protocol requirements.

    Checks both structural (protocol) and metadata compliance.
    """

    def validate_plugin(self, plugin: Any, group: str) -> bool:
        """
        Validate plugin conforms to its protocol.

        Args:
            plugin: Plugin class or instance
            group: Entry point group

        Returns:
            True if valid, False otherwise
        """
        # Check if plugin has metadata
        if not self._validate_metadata(plugin):
            return False

        # Check protocol compliance
        if not self._validate_protocol(plugin, group):
            return False

        # Additional validation
        if not self._validate_aip_version(plugin):
            return False

        return True

    def _validate_metadata(self, plugin: Any) -> bool:
        """Check plugin has valid metadata."""
        # Check if plugin has plugin_metadata method
        if not hasattr(plugin, 'plugin_metadata') or not callable(getattr(plugin, 'plugin_metadata')):
            logger.error(
                f"Plugin {plugin} does not implement plugin_metadata() method"
            )
            return False

        try:
            metadata = plugin.plugin_metadata()

            # Required fields
            required = ['name', 'aip_version']
            for field in required:
                if field not in metadata:
                    logger.error(f"Plugin metadata missing required field: {field}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Error getting plugin metadata: {e}")
            return False

    def _validate_protocol(self, plugin: Any, group: str) -> bool:
        """Check plugin conforms to group protocol."""
        protocol_map = _get_protocol_map()
        protocol = protocol_map.get(group)
        if protocol is None:
            logger.warning(f"No protocol defined for group '{group}'")
            return True  # Allow if no protocol defined

        # Perform structural checking for protocol conformance
        # runtime_checkable protocols don't work well with isinstance on classes
        if not self._check_protocol_structure(plugin, protocol):
            logger.error(
                f"Plugin does not conform to {protocol.__name__} for group '{group}'"
            )
            return False

        return True

    def _check_protocol_structure(self, plugin: Any, protocol: type) -> bool:
        """
        Check if plugin structurally conforms to protocol.

        Works with both classes and instances by checking for required
        attributes and methods defined in the protocol.
        """
        # Get protocol annotations to check required attributes
        protocol_attrs = getattr(protocol, '__annotations__', {})

        # Check all required attributes exist on the plugin
        # Skip Optional attributes (type is Union[X, None])
        for attr_name, attr_type in protocol_attrs.items():
            # Check if this is an Optional type (Union with None)
            if self._is_optional_type(attr_type):
                continue  # Optional attributes are not required

            if not hasattr(plugin, attr_name):
                return False

        # Check all required methods exist and are callable
        # Only check methods defined directly in the protocol, not inherited
        for attr_name, attr_value in inspect.getmembers(protocol):
            # Skip private/special methods
            if attr_name.startswith('_'):
                continue

            # Skip class variables (already checked via annotations)
            if attr_name in protocol_attrs:
                continue

            # Check if this is a method defined in the protocol
            if inspect.isfunction(attr_value) or inspect.ismethod(attr_value):
                if not hasattr(plugin, attr_name):
                    return False
                plugin_attr = getattr(plugin, attr_name)
                if not callable(plugin_attr):
                    return False

        return True

    def _is_optional_type(self, type_hint: Any) -> bool:
        """Check if a type hint is Optional (Union[X, None])."""
        origin = get_origin(type_hint)
        if origin is Union:
            args = get_args(type_hint)
            # Optional[X] is Union[X, None]
            return type(None) in args
        return False

    def _validate_aip_version(self, plugin: Any) -> bool:
        """Check AIP version is supported."""
        try:
            metadata = plugin.plugin_metadata()
            aip_version = metadata.get('aip_version')

            # Currently only support AIP-001
            if aip_version != '001':
                logger.warning(
                    f"Plugin uses unsupported AIP version: {aip_version}"
                )
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating AIP version: {e}")
            return False

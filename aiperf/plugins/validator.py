# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Plugin Validator (AIP-001)

Validates plugins conform to their respective protocols.
Ensures type safety and contract compliance.
"""

from typing import Any

from aiperf.common.aiperf_logger import AIPerfLogger
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


PROTOCOL_MAP = {
    "aiperf.metric": MetricPluginProtocol,
    "aiperf.endpoint": EndpointPluginProtocol,
    "aiperf.data_exporter": DataExporterPluginProtocol,
    "aiperf.transport": TransportPluginProtocol,
    "aiperf.processor": ProcessorPluginProtocol,
    "aiperf.collector": CollectorPluginProtocol,
}


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
        if not isinstance(plugin, PluginMetadataProtocol):
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
        protocol = PROTOCOL_MAP.get(group)
        if protocol is None:
            logger.warning(f"No protocol defined for group '{group}'")
            return True  # Allow if no protocol defined

        if not isinstance(plugin, protocol):
            logger.error(
                f"Plugin does not conform to {protocol.__name__} for group '{group}'"
            )
            return False

        return True

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

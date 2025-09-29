# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Hook specifications for request converter plugins."""

from typing import Any

import pluggy

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.enums import EndpointType
from aiperf.common.models import Turn

# Define the project name for the pluggy system
PROJECT_NAME = "aiperf"

# Create the hookspec marker for defining hook specifications
hookspec = pluggy.HookspecMarker(PROJECT_NAME)


class RequestConverterHookSpec:
    """Hook specifications for request converter plugins."""

    @hookspec
    def get_supported_endpoint_types(self) -> list[EndpointType]:
        """Return the list of endpoint types this plugin supports.

        Returns:
            List of EndpointType enums that this plugin can handle.
        """

    @hookspec
    def get_plugin_name(self) -> str:
        """Return the name of this plugin.

        Returns:
            A unique string identifier for this plugin.
        """

    @hookspec
    def get_plugin_priority(self) -> int:
        """Return the priority of this plugin.

        Higher priority plugins are preferred when multiple plugins
        support the same endpoint type.

        Returns:
            Integer priority (higher = more preferred). Default: 0.
        """

    @hookspec
    async def format_payload(
        self,
        endpoint_type: EndpointType,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any] | None:
        """Format a payload for the specified endpoint type.

        Args:
            endpoint_type: The type of endpoint to format for.
            model_endpoint: Information about the model endpoint.
            turn: The turn data to format.

        Returns:
            Formatted payload dict if this plugin handles the endpoint_type,
            None otherwise.
        """

    @hookspec
    def can_handle_endpoint_type(self, endpoint_type: EndpointType) -> bool:
        """Check if this plugin can handle the specified endpoint type.

        Args:
            endpoint_type: The endpoint type to check.

        Returns:
            True if this plugin can handle the endpoint type, False otherwise.
        """

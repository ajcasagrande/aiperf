# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Any

import orjson

from aiperf.clients.http.aiohttp_client import AioHttpClientMixin
from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.enums import EndpointType
from aiperf.common.factories import InferenceClientFactory, RequestConverterFactory
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.models import RequestRecord, Turn


@RequestConverterFactory.register(EndpointType.NONE)
class NoneRequestConverter(AIPerfLoggerMixin):
    """Request converter for none endpoint."""

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any]:
        """Format payload for a none request."""
        return {}


@InferenceClientFactory.register(EndpointType.NONE)
class NoneClient(AioHttpClientMixin):
    """Client for none endpoint."""

    def __init__(self, model_endpoint: ModelEndpointInfo, **kwargs) -> None:
        super().__init__(model_endpoint, **kwargs)

    async def send_request(
        self,
        model_endpoint: ModelEndpointInfo,
        payload: dict[str, Any],
    ) -> RequestRecord:
        """Send a request to the none endpoint."""
        return await super().post_request(
            self.get_url(model_endpoint),
            orjson.dumps(payload).decode("utf-8"),
            self.get_headers(model_endpoint),
        )

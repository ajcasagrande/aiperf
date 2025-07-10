# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
from typing import Any

from aiperf.clients.client_interfaces import (
    RequestConverterFactory,
    RequestConverterProtocol,
)
from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.dataset_models import Turn
from aiperf.common.enums import EndpointType


@RequestConverterFactory.register(EndpointType.OPENAI_EMBEDDINGS)
class OpenAIEmbeddingsRequestConverter(RequestConverterProtocol[dict[str, Any]]):
    """Request converter for OpenAI Embeddings requests."""

    def __init__(self) -> None:
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any]:
        """Format payload for an embeddings request."""

        payload = {
            "input": turn.text,
            "model": model_endpoint.primary_model_name,
            "dimensions": model_endpoint.endpoint.url_params.get("dimensions", 1536)
            if model_endpoint.endpoint.url_params
            else 1536,
            "encoding_format": model_endpoint.endpoint.url_params.get(
                "encoding_format", "float"
            )
            if model_endpoint.endpoint.url_params
            else "float",
            "user": model_endpoint.endpoint.url_params.get("user", "")
            if model_endpoint.endpoint.url_params
            else "",
            "stream": model_endpoint.endpoint.streaming,
        }

        if model_endpoint.endpoint.extra:
            payload.update(model_endpoint.endpoint.extra)

        self.logger.debug("Formatted payload: %s", payload)
        return payload

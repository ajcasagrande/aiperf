#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Any

from _typeshed import Incomplete

from aiperf.clients.client_interfaces import (
    RequestConverterFactory as RequestConverterFactory,
)
from aiperf.clients.model_endpoint_info import ModelEndpointInfo as ModelEndpointInfo
from aiperf.common.dataset_models import Turn as Turn
from aiperf.common.enums import EndpointType as EndpointType

class OpenAICompletionRequestConverter:
    logger: Incomplete
    def __init__(self) -> None: ...
    async def format_payload(
        self, model_endpoint: ModelEndpointInfo, turn: Turn
    ) -> dict[str, Any]: ...

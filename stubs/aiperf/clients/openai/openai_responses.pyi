#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Any

from _typeshed import Incomplete

from aiperf.clients.model_endpoint_info import ModelEndpointInfo as ModelEndpointInfo
from aiperf.common.models import Turn as Turn

class OpenAIResponsesRequestConverter:
    logger: Incomplete
    def __init__(self) -> None: ...
    async def format_payload(
        self, model_endpoint: ModelEndpointInfo, turn: Turn
    ) -> dict[str, Any]: ...

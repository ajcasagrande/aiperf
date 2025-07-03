# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from collections.abc import Callable, Coroutine
from typing import Any, Protocol

from aiperf.common.messages import (
    ConversationResponseMessage,
    CreditDropMessage,
    InferenceResultsMessage,
    WorkerHealthMessage,
)


class WorkerCommunicationsProtocol(Protocol):
    """Protocol for a worker service that handles communications."""

    def register_credit_drop_handler(
        self,
        handler: Callable[[CreditDropMessage], Coroutine[Any, Any, None]],
    ) -> None:
        """Register a handler for credit drop messages."""
        ...

    def return_credits(self, amount: int) -> Coroutine[Any, Any, None]:
        """Return credits to the Timing Manager."""
        ...

    def request_conversation_data(
        self,
        conversation_id: str | None = None,
    ) -> Coroutine[Any, Any, ConversationResponseMessage]:
        """Request conversation data for a given conversation ID."""
        ...

    def push_inference_results(
        self,
        message: InferenceResultsMessage,
    ) -> Coroutine[Any, Any, None]:
        """Push inference results to the inference results client."""
        ...

    def publish_health_message(
        self,
        message: WorkerHealthMessage,
    ) -> Coroutine[Any, Any, None]:
        """Publish a health message to the Worker Manager."""
        ...

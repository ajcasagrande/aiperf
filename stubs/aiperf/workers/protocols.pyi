#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from collections.abc import Callable as Callable
from collections.abc import Coroutine
from typing import Any, Protocol

from aiperf.common.messages import (
    ConversationResponseMessage as ConversationResponseMessage,
)
from aiperf.common.messages import CreditDropMessage as CreditDropMessage
from aiperf.common.messages import InferenceResultsMessage as InferenceResultsMessage
from aiperf.common.messages import WorkerHealthMessage as WorkerHealthMessage

class WorkerCommunicationsProtocol(Protocol):
    def register_credit_drop_handler(
        self, handler: Callable[[CreditDropMessage], Coroutine[Any, Any, None]]
    ) -> None: ...
    def return_credits(self, amount: int) -> Coroutine[Any, Any, None]: ...
    def request_conversation_data(
        self, conversation_id: str | None = None
    ) -> Coroutine[Any, Any, ConversationResponseMessage]: ...
    def push_inference_results(
        self, message: InferenceResultsMessage
    ) -> Coroutine[Any, Any, None]: ...
    def publish_health_message(
        self, message: WorkerHealthMessage
    ) -> Coroutine[Any, Any, None]: ...

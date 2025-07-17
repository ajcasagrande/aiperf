#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Literal

from aiperf.common.dataset_models import Conversation as Conversation
from aiperf.common.dataset_models import Turn as Turn
from aiperf.common.enums import CreditPhase as CreditPhase
from aiperf.common.enums import MessageType as MessageType
from aiperf.common.messages._base import BaseServiceMessage as BaseServiceMessage

class ConversationRequestMessage(BaseServiceMessage):
    message_type: Literal[MessageType.CONVERSATION_REQUEST]
    conversation_id: str | None
    credit_phase: CreditPhase | None

class ConversationResponseMessage(BaseServiceMessage):
    message_type: Literal[MessageType.CONVERSATION_RESPONSE]
    conversation: Conversation

class ConversationTurnRequestMessage(BaseServiceMessage):
    message_type: Literal[MessageType.CONVERSATION_TURN_REQUEST]
    conversation_id: str
    turn_index: int

class ConversationTurnResponseMessage(BaseServiceMessage):
    message_type: Literal[MessageType.CONVERSATION_TURN_RESPONSE]
    turn: Turn

class DatasetTimingRequest(BaseServiceMessage):
    message_type: Literal[MessageType.DATASET_TIMING_REQUEST]

class DatasetTimingResponse(BaseServiceMessage):
    message_type: Literal[MessageType.DATASET_TIMING_RESPONSE]
    timing_data: list[tuple[int, str]]

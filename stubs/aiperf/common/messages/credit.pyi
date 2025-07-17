#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Literal

from aiperf.common.enums import CreditPhase as CreditPhase
from aiperf.common.enums import MessageType as MessageType
from aiperf.common.messages.base import BaseServiceMessage as BaseServiceMessage

class CreditDropMessage(BaseServiceMessage):
    message_type: Literal[MessageType.CREDIT_DROP]
    phase: CreditPhase
    conversation_id: str | None
    credit_drop_ns: int | None

class CreditReturnMessage(BaseServiceMessage):
    message_type: Literal[MessageType.CREDIT_RETURN]
    phase: CreditPhase
    delayed_ns: int | None
    pre_inference_ns: int | None
    @property
    def delayed(self) -> bool: ...

class CreditPhaseStartMessage(BaseServiceMessage):
    message_type: Literal[MessageType.CREDIT_PHASE_START]
    phase: CreditPhase
    start_ns: int
    total_expected_requests: int | None
    expected_duration_sec: float | None

class CreditPhaseProgressMessage(BaseServiceMessage):
    message_type: Literal[MessageType.CREDIT_PHASE_PROGRESS]
    phase: CreditPhase
    sent: int
    completed: int

class CreditPhaseSendingCompleteMessage(BaseServiceMessage):
    message_type: Literal[MessageType.CREDIT_PHASE_SENDING_COMPLETE]
    phase: CreditPhase
    sent_end_ns: int | None

class CreditPhaseCompleteMessage(BaseServiceMessage):
    message_type: Literal[MessageType.CREDIT_PHASE_COMPLETE]
    phase: CreditPhase
    end_ns: int | None

class CreditsCompleteMessage(BaseServiceMessage):
    message_type: Literal[MessageType.CREDITS_COMPLETE]

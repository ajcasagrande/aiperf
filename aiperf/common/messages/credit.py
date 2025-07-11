# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Literal

from pydantic import Field

from aiperf.common.credit_models import CreditPhaseStats
from aiperf.common.enums import CreditPhase, MessageType
from aiperf.common.messages.base import (
    BaseServiceMessage,
    RequiresRequestNSMixin,
)


class BasePhaseStatsMessage(BaseServiceMessage, RequiresRequestNSMixin):
    """Base message for phase stats. Sent by the TimingManager to report stats of a credit phase."""

    phase_stats: CreditPhaseStats = Field(
        ...,
        description="The credit phase stats for the phase",
    )


class CreditPhaseProgressMessage(BaseServiceMessage, RequiresRequestNSMixin):
    """Sent by the TimingManager to report the stats of ALL credit phases."""

    message_type: Literal[MessageType.CREDIT_PHASE_PROGRESS] = (
        MessageType.CREDIT_PHASE_PROGRESS
    )

    phase_stats_map: dict[CreditPhase, CreditPhaseStats] = Field(
        ...,
        description="The credit phase stats for all phases",
    )


class CreditPhaseStartMessage(BasePhaseStatsMessage):
    """Message for credit phase start. Sent by the TimingManager to report that a credit phase has started."""

    message_type: Literal[MessageType.CREDIT_PHASE_START] = (
        MessageType.CREDIT_PHASE_START
    )


class CreditPhaseCompleteMessage(BasePhaseStatsMessage):
    """Message for credit phase complete. Sent by the TimingManager to report that a credit phase has completed."""

    message_type: Literal[MessageType.CREDIT_PHASE_COMPLETE] = (
        MessageType.CREDIT_PHASE_COMPLETE
    )


class CreditPhaseSendingCompleteMessage(BasePhaseStatsMessage):
    """Message for credit phase sending complete. Sent by the TimingManager to report that a credit phase has completed sending."""

    message_type: Literal[MessageType.CREDIT_PHASE_SENDING_COMPLETE] = (
        MessageType.CREDIT_PHASE_SENDING_COMPLETE
    )


class CreditDropMessage(BaseServiceMessage):
    """Message indicating that a credit has been dropped.
    This message is sent by the timing manager to workers to indicate that credit(s)
    have been dropped.
    """

    message_type: Literal[MessageType.CREDIT_DROP] = MessageType.CREDIT_DROP

    credit_phase: CreditPhase = Field(..., description="The type of credit phase")
    conversation_id: str | None = Field(
        default=None, description="The ID of the conversation, if applicable."
    )
    credit_drop_ns: int | None = Field(
        default=None,
        description="Timestamp of the credit drop, if applicable. None means send ASAP.",
    )


class CreditReturnMessage(BaseServiceMessage):
    """Message indicating that a credit has been returned.
    This message is sent by a worker to the timing manager to indicate that work has
    been completed.
    """

    message_type: Literal[MessageType.CREDIT_RETURN] = MessageType.CREDIT_RETURN

    credit_phase: CreditPhase = Field(
        ...,
        description="The type of credit phase",
    )
    conversation_id: str | None = Field(
        default=None, description="The ID of the conversation, if applicable."
    )
    credit_drop_ns: int | None = Field(
        default=None,
        description="Timestamp of the original credit drop, if applicable.",
    )
    delayed_ns: int | None = Field(
        default=None,
        ge=1,
        description="The number of nanoseconds the credit drop was delayed by, or None if the credit was sent on time.",
    )

    @property
    def delayed(self) -> bool:
        return self.delayed_ns is not None


class CreditsCompleteMessage(BaseServiceMessage):
    """Credits complete message sent by the TimingManager to the System controller to signify all requests have completed."""

    message_type: Literal[MessageType.CREDITS_COMPLETE] = MessageType.CREDITS_COMPLETE
    cancelled: bool = Field(
        default=False,
        description="Whether the profile run was cancelled",
    )

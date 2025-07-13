# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


from typing import Literal

from pydantic import Field

from aiperf.common.credit_models import PhaseProcessingStats
from aiperf.common.enums import CreditPhase, MessageType
from aiperf.common.messages.base import BaseServiceMessage


class RecordsProcessingStatsMessage(BaseServiceMessage):
    """Message for processing stats. Sent by the RecordsManager to report the stats of the profile run.
    This contains the stats for a single credit phase only."""

    message_type: Literal[MessageType.PROCESSING_STATS] = MessageType.PROCESSING_STATS

    phase: CreditPhase = Field(..., description="The credit phase")
    processing_stats: PhaseProcessingStats = Field(
        ..., description="The stats for the credit phase"
    )
    worker_stats: dict[str, PhaseProcessingStats] = Field(
        default_factory=dict,
        description="The stats for each worker how many requests were processed and how many errors were "
        "encountered, keyed by worker service_id",
    )

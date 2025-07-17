#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Literal

from aiperf.common.credit_models import PhaseProcessingStats as PhaseProcessingStats
from aiperf.common.enums import CreditPhase as CreditPhase
from aiperf.common.enums import MessageType as MessageType
from aiperf.common.messages._base import BaseServiceMessage as BaseServiceMessage

class RecordsProcessingStatsMessage(BaseServiceMessage):
    message_type: Literal[MessageType.PROCESSING_STATS]
    phase: CreditPhase
    processing_stats: PhaseProcessingStats
    worker_stats: dict[str, PhaseProcessingStats]

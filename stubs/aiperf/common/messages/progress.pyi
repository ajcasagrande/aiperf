#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Literal

from pydantic import SerializeAsAny as SerializeAsAny

from aiperf.common.enums import MessageType as MessageType
from aiperf.common.messages.base import BaseServiceMessage as BaseServiceMessage
from aiperf.common.record_models import ErrorDetailsCount as ErrorDetailsCount
from aiperf.common.record_models import MetricResult as MetricResult

class ProfileResultsMessage(BaseServiceMessage):
    message_type: Literal[MessageType.PROFILE_RESULTS]
    records: SerializeAsAny[list[MetricResult]]
    total: int
    completed: int
    start_ns: int
    end_ns: int
    was_cancelled: bool
    errors_by_type: list[ErrorDetailsCount]

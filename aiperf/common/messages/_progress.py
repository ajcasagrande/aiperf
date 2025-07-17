# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Literal

from pydantic import Field, SerializeAsAny

from aiperf.common.enums import MessageType
from aiperf.common.messages._base import BaseServiceMessage
from aiperf.common.record_models import ErrorDetailsCount, MetricResult


class ProfileResultsMessage(BaseServiceMessage):
    """Message for profile results."""

    message_type: Literal[MessageType.PROFILE_RESULTS] = MessageType.PROFILE_RESULTS

    records: SerializeAsAny[list[MetricResult]] = Field(
        ..., description="The records of the profile results"
    )
    total: int = Field(
        ...,
        description="The total number of inference requests expected to be made (if known)",
    )
    completed: int = Field(
        ..., description="The number of inference requests completed"
    )
    start_ns: int = Field(
        ..., description="The start time of the profile run in nanoseconds"
    )
    end_ns: int = Field(
        ..., description="The end time of the profile run in nanoseconds"
    )
    was_cancelled: bool = Field(
        default=False,
        description="Whether the profile run was cancelled early",
    )
    errors_by_type: list[ErrorDetailsCount] = Field(
        default_factory=list,
        description="A list of the unique error details and their counts",
    )


# class ProfileProgressMessage(BaseServiceMessage):
#     """Message for profile progress. Sent by the timing manager to the system controller
#     to report the progress of the profile run."""

#     message_type: Literal[MessageType.PROFILE_PROGRESS] = MessageType.PROFILE_PROGRESS

#     profile_id: str | None = Field(
#         default=None, description="The ID of the current profile"
#     )
#     start_ns: int = Field(
#         ..., description="The start time of the profile run in nanoseconds"
#     )
#     measurement_start_ns: int = Field(
#         ...,
#         description="The start time for steady-state measurement in nanoseconds (after ramp-up)",
#     )
#     end_ns: int | None = Field(
#         default=None, description="The end time of the profile run in nanoseconds"
#     )
#     phase_credits: dict[CreditPhase, CreditPhaseStats] = Field(
#         default_factory=dict,
#         description="The stats for each credit phase how many credits were dropped and how many were returned",
#     )
#     total: int = Field(
#         ..., description="The total number of inference requests to be made (if known)"
#     )
#     completed: int = Field(
#         ..., description="The number of inference requests completed"
#     )
#     ramp_up_completed: int = Field(
#         default=0,
#         description="The number of inference requests completed during ramp-up phase",
#     )
#     credit_phase: CreditPhase = Field(
#         default=CreditPhase.STEADY_STATE,
#         description="The type of credit phase (either warmup or profiling)",
#     )

#     @property
#     def steady_state_completed(self) -> int:
#         """Calculate the number of requests completed during steady-state (after ramp-up)."""
#         return max(0, self.completed - self.ramp_up_completed)

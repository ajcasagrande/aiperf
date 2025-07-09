# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

# from typing import Literal

# from pydantic import Field

# from aiperf.common.enums import CaseInsensitiveStrEnum, MessageType
# from aiperf.common.messages import BaseServiceMessage
# from aiperf.common.pydantic_utils import AIPerfBaseModel
# from aiperf.progress.progress_models import ProfileProgress


# class SweepCompletionTrigger(CaseInsensitiveStrEnum):
#     """Determines how the sweep completion is determined in order to know how to track the progress."""

#     COMPLETED_PROFILES = "completed_profiles"
#     """The sweep will run until all profiles are completed."""

#     STABILIZATION_BASED = "stabilization_based"
#     """The sweep will run until the metrics stabilize. TDB"""

#     GOODPUT_THRESHOLD = "goodput_threshold"
#     """The sweep will run until the goodput threshold is met. TDB"""

#     CUSTOM = "custom"
#     """User defined trigger. TBD"""


# class SweepParamType(CaseInsensitiveStrEnum):
#     """Determines the type of sweep parameter."""

#     INT = "int"
#     """The parameter is an integer."""

#     FLOAT = "float"
#     """The parameter is a float."""

#     STRING = "string"
#     """The parameter is a string."""

#     BOOLEAN = "boolean"
#     """The parameter is a boolean."""

#     CUSTOM = "custom"
#     """User defined parameter type. TBD"""


# class SweepParamOrder(CaseInsensitiveStrEnum):
#     """Determines the order in which the sweep parameters are tested."""

#     ASCENDING = "ascending"
#     """The parameters are tested in ascending order."""

#     DESCENDING = "descending"
#     """The parameters are tested in descending order."""

#     RANDOM = "random"
#     """The parameters are tested in random order. TBD"""

#     CUSTOM = "custom"
#     """User defined order. TBD"""


# class SweepMultiParamOrder(CaseInsensitiveStrEnum):
#     """Determines the order in which the sweep parameters are tested for a multi-parameter sweep.
#     This is only applicable for multi-parameter sweeps."""

#     DEPTH_FIRST = "depth_first"
#     """The parameters are tested in depth-first order."""

#     BREADTH_FIRST = "breadth_first"
#     """The parameters are tested in breadth-first order."""

#     RANDOM = "random"
#     """The parameters are tested in random order. TBD"""

#     CUSTOM = "custom"
#     """User defined order. TBD"""


# class SweepProgress(AIPerfBaseModel):
#     """State of the sweep progress."""

#     sweep_id: str = Field(..., description="The ID of the current sweep")
#     sweep_completion_trigger: SweepCompletionTrigger = Field(
#         default=SweepCompletionTrigger.COMPLETED_PROFILES,
#         description="The trigger of sweep completion",
#     )
#     profiles: list[ProfileProgress] = Field(
#         default_factory=list, description="The state of the profiles in the sweep"
#     )
#     current_profile_idx: int | None = Field(
#         default=None,
#         description="The index of the current profile. If it has not been started, this will be None.",
#     )
#     completed_profiles: int = Field(
#         default=0, description="The number of completed profiles in the sweep"
#     )
#     start_time_ns: int | None = Field(
#         default=None,
#         description="The start time of the sweep in nanoseconds. If it has not been started, this will be None.",
#     )
#     end_time_ns: int | None = Field(
#         default=None,
#         description="The end time of the sweep in nanoseconds. If it has not been completed, this will be None.",
#     )
#     was_cancelled: bool = Field(
#         default=False,
#         description="Whether the sweep was cancelled early",
#     )

#     @property
#     def current_profile(self) -> ProfileProgress | None:
#         if self.current_profile_idx is None:
#             return None
#         return self.profiles[self.current_profile_idx]

#     def next_profile(self) -> ProfileProgress | None:
#         if self.current_profile_idx is None:
#             self.current_profile_idx = 0
#         else:
#             self.current_profile_idx += 1

#         if self.current_profile_idx >= len(self.profiles):
#             return None

#         return self.profiles[self.current_profile_idx]


# class SweepProgressMessage(BaseServiceMessage):
#     """Message for sweep progress."""

#     # TODO: add profile information

#     message_type: Literal[MessageType.SWEEP_PROGRESS] = MessageType.SWEEP_PROGRESS

#     sweep_id: str = Field(..., description="The ID of the current sweep")
#     sweep_start_ns: int = Field(
#         ..., description="The start time of the sweep in nanoseconds"
#     )
#     sweep_end_ns: int | None = Field(
#         default=None, description="The end time of the sweep in nanoseconds"
#     )

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import uuid
from typing import Any

from pydantic import BaseModel, Field

from aiperf.common.enums import SweepCompletionTrigger, SweepParamOrder


class SweepParamConfig(BaseModel):
    """Configuration for a sweep parameter."""

    param_name: str = Field(
        ...,
        description="The name of the parameter",
    )
    param_values: list[Any] = Field(
        ...,
        description="The values of the parameter",
    )
    param_order: SweepParamOrder = Field(
        default=SweepParamOrder.ASCENDING,
        description="The order in which the parameter values are applied",
    )


class ProfileConfig(BaseModel):
    """Configuration for a profile."""

    profile_id: str = Field(
        default=str(uuid.uuid4()),
        description="The ID of the profile",
    )


class SweepConfig(BaseModel):
    """Configuration for a sweep."""

    sweep_id: str = Field(
        default=str(uuid.uuid4()),
        description="The ID of the sweep",
    )
    completion_trigger: SweepCompletionTrigger = Field(
        default=SweepCompletionTrigger.COMPLETED_PROFILES,
        description="The trigger for the sweep to complete",
    )
    base_profile: ProfileConfig = Field(
        ...,
        description="The base profile to use for the sweep",
    )
    sweep_params: list[SweepParamConfig] = Field(
        default_factory=list,
        description="The parameters to sweep",
    )


class BenchmarkSuiteConfig(BaseModel):
    """Configuration for a benchmark suite."""

    sweeps: list[SweepConfig] = Field(
        default_factory=list,
        description="The sweeps to run",
    )
    profiles: list[ProfileConfig] = Field(
        default_factory=list,
        description="The profiles to run",
    )

#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

from pydantic import BaseModel, Field, SerializeAsAny

from aiperf.common.enums import (
    BenchmarkSuiteCompletionTrigger,
    BenchmarkSuiteType,
    ProfileCompletionTrigger,
    SweepCompletionTrigger,
)
from aiperf.common.models.record_models import ErrorDetailsCount, ResultsRecord

################################################################################
# Progress Models
################################################################################


class ProfileProgress(BaseModel):
    """State of the profile progress."""

    profile_id: str = Field(..., description="The ID of the profile")

    profile_completion_trigger: ProfileCompletionTrigger = Field(
        default=ProfileCompletionTrigger.UNKNOWN,
        description="The trigger of profile completion",
    )

    start_time_ns: int = Field(
        ..., description="The start time of the profile run in nanoseconds"
    )
    end_time_ns: int | None = Field(
        default=None,
        description="The end time of the profile run in nanoseconds. If it has not been completed, this will be None.",
    )

    total_expected_requests: int | None = Field(
        default=None,
        description="The total number of inference requests to be made. This will be None if the profile completion trigger is not request-based.",
    )
    requests_completed: int = Field(
        default=0,
        description="The number of inference requests completed during the profile run",
    )
    request_errors: int = Field(
        default=0,
        description="The total number of request errors encountered during the profile run",
    )
    successful_requests: int = Field(
        default=0,
        description="The total number of successful requests completed during the profile run",
    )
    requests_processed: int = Field(
        default=0,
        description="The total number of requests processed by the records manager "
        "during the profile run. This can be less than the requests_completed if "
        "the records manager processing requests is slower than the inference requests "
        "are being made.",
    )
    requests_per_second: float | None = Field(
        default=None,
        description="The number of requests completed per second during the profile run",
    )
    processed_per_second: float | None = Field(
        default=None,
        description="The number of requests processed by the records manager per second during the profile run",
    )
    worker_completed: dict[str, int] = Field(
        default_factory=dict,
        description="Per-worker request completion counts, keyed by worker service_id during the profile run",
    )
    worker_errors: dict[str, int] = Field(
        default_factory=dict,
        description="Per-worker error counts, keyed by worker service_id during the profile run",
    )
    was_cancelled: bool = Field(
        default=False,
        description="Whether the profile run was cancelled early",
    )
    elapsed_time: float = Field(
        default=0,
        description="The elapsed time of the profile run in seconds",
    )
    eta: float | None = Field(
        default=None,
        description="The estimated time remaining for the profile run in seconds",
    )
    records: SerializeAsAny[list[ResultsRecord]] = Field(
        default_factory=list, description="The records of the profile results"
    )
    errors_by_type: list[ErrorDetailsCount] = Field(
        default_factory=list,
        description="A list of the unique error details and their counts",
    )
    is_complete: bool = Field(
        default=False,
        description="Whether the profile run is complete",
    )


class SweepProgress(BaseModel):
    """State of the sweep progress."""

    sweep_id: str = Field(..., description="The ID of the current sweep")
    sweep_completion_trigger: SweepCompletionTrigger = Field(
        default=SweepCompletionTrigger.UNKNOWN,
        description="The trigger of sweep completion",
    )
    profiles: dict[str, ProfileProgress] = Field(
        default_factory=dict, description="The state of the profiles in the sweep"
    )
    current_profile_id: str | None = Field(
        default=None,
        description="The ID of the current profile. If it has not been started, this will be None.",
    )
    completed_profiles: int = Field(
        default=0, description="The number of completed profiles in the sweep"
    )
    start_time_ns: int | None = Field(
        default=None,
        description="The start time of the sweep in nanoseconds. If it has not been started, this will be None.",
    )
    end_time_ns: int | None = Field(
        default=None,
        description="The end time of the sweep in nanoseconds. If it has not been completed, this will be None.",
    )
    was_cancelled: bool = Field(
        default=False,
        description="Whether the sweep was cancelled early",
    )

    @property
    def current_profile(self) -> ProfileProgress | None:
        if self.current_profile_id is None:
            return None
        return self.profiles.get(self.current_profile_id)


class BenchmarkSuiteProgress(BaseModel):
    """State of the suite progress."""

    suite_type: BenchmarkSuiteType = Field(
        default=BenchmarkSuiteType.SINGLE_PROFILE,
        description="The type of suite. Default is SINGLE_PROFILE.",
    )
    suite_completion_trigger: BenchmarkSuiteCompletionTrigger = Field(
        default=BenchmarkSuiteCompletionTrigger.UNKNOWN,
        description="The trigger of suite completion",
    )
    start_time_ns: int | None = Field(
        default=None,
        description="The overall start time of the suite in nanoseconds. If it has not been started, this will be None.",
    )
    end_time_ns: int | None = Field(
        default=None,
        description="The overall end time of the suite in nanoseconds. If it has not been completed, this will be None.",
    )
    was_cancelled: bool = Field(
        default=False,
        description="Whether the suite was cancelled early",
    )

    @property
    def current_sweep(self) -> SweepProgress | None:
        if not isinstance(self, SweepSuiteProgress) or self.current_sweep_id is None:
            return None
        return self.sweeps.get(self.current_sweep_id)

    @property
    def current_profile(self) -> ProfileProgress | None:
        if isinstance(self, ProfileSuiteProgress):
            if self.current_profile_id is None:
                return None
            return self.profiles.get(self.current_profile_id)

        elif isinstance(self, SweepSuiteProgress):
            if self.current_sweep is None:
                return None
            return self.current_sweep.current_profile

        return None

    @current_profile.setter
    def current_profile(self, profile: ProfileProgress) -> None:
        """Set the current profile."""
        if isinstance(self, ProfileSuiteProgress):
            self.current_profile_id = profile.profile_id
            self.profiles[self.current_profile_id] = profile
        elif isinstance(self, SweepSuiteProgress):
            if self.current_sweep is None:
                raise ValueError("Current sweep is not set")
            self.current_sweep.current_profile_id = profile.profile_id
            self.current_sweep.profiles[self.current_sweep.current_profile_id] = profile
        else:
            raise ValueError(f"Invalid suite type: {type(self)}")


class ProfileSuiteProgress(BenchmarkSuiteProgress):
    """State of a profile based suite with 1 or more profile runs."""

    profiles: dict[str, ProfileProgress] = Field(
        default_factory=dict, description="The state of the profiles in the suite"
    )
    total_profiles: int = Field(default=0, description="The total number of profiles")
    completed_profiles: int = Field(
        default=0, description="The number of completed profiles"
    )
    current_profile_id: str | None = Field(
        default=None,
        description="The ID of the current profile run. If it has not been started, this will be None.",
    )


class SweepSuiteProgress(BenchmarkSuiteProgress):
    """State of a sweep based suite with 1 or more sweep runs."""

    sweeps: dict[str, SweepProgress] = Field(
        default_factory=dict, description="The state of the sweeps in the suite"
    )
    total_sweeps: int = Field(default=0, description="The total number of sweeps")
    completed_sweeps: int = Field(
        default=0, description="The number of completed sweeps"
    )
    current_sweep_id: str | None = Field(
        default=None,
        description="The ID of the current sweep. If it has not been started, this will be None.",
    )

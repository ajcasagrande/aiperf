# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


# class ProfileProgress(AIPerfBaseModel):
#     """State of the profile progress."""

#     profile_id: str = Field(..., description="The ID of the profile")

#     profile_completion_trigger: ProfileCompletionTrigger = Field(
#         default=ProfileCompletionTrigger.REQUEST_COUNT,
#         description="The trigger of profile completion",
#     )

#     start_time_ns: int | None = Field(
#         default=None,
#         description="The start time of the profile run in nanoseconds. "
#         "If it has not been started, this will be None.",
#     )
#     measurement_start_time_ns: int | None = Field(
#         default=None,
#         description="The start time for steady-state measurement in nanoseconds (after ramp-up). "
#         "If None, falls back to start_time_ns.",
#     )
#     end_time_ns: int | None = Field(
#         default=None,
#         description="The end time of the profile run in nanoseconds. "
#         "If it has not been completed, this will be None.",
#     )
#     phase_credits: dict[CreditPhase, CreditPhaseStats] = Field(
#         default_factory=dict,
#         description="The stats for each credit phase how many credits were dropped and how many were returned. "
#         "If None, the phase has not started.",
#     )

#     total_expected_requests: int | None = Field(
#         default=None,
#         description="The total number of inference requests to be made. "
#         "This will be None if the profile completion trigger is not request-based.",
#     )
#     requests_completed: int = Field(
#         default=0,
#         description="The number of inference requests completed during the profile run",
#     )
#     ramp_up_completed: int = Field(
#         default=0,
#         description="The number of inference requests completed during ramp-up phase",
#     )
#     request_errors: int = Field(
#         default=0,
#         description="The total number of request errors encountered during the profile run",
#     )
#     successful_requests: int = Field(
#         default=0,
#         description="The total number of successful requests completed during the profile run",
#     )
#     requests_processed: int = Field(
#         default=0,
#         description="The total number of requests processed by the records manager "
#         "during the profile run. This can be less than the requests_completed if "
#         "the records manager processing requests is slower than the inference requests "
#         "are being made.",
#     )
#     requests_per_second: float | None = Field(
#         default=None,
#         description="The number of requests completed per second during the profile run",
#     )
#     processed_per_second: float | None = Field(
#         default=None,
#         description="The number of requests processed by the records manager per second during the profile run",
#     )
#     worker_completed: dict[str, int] = Field(
#         default_factory=dict,
#         description="Per-worker request completion counts, keyed by worker service_id during the profile run",
#     )
#     worker_errors: dict[str, int] = Field(
#         default_factory=dict,
#         description="Per-worker error counts, keyed by worker service_id during the profile run",
#     )
#     was_cancelled: bool = Field(
#         default=False,
#         description="Whether the profile run was cancelled early",
#     )
#     elapsed_time: float = Field(
#         default=0,
#         description="The elapsed time of the profile run in seconds",
#     )
#     eta: float | None = Field(
#         default=None,
#         description="The estimated time remaining for the profile run in seconds",
#     )
#     processing_eta: float | None = Field(
#         default=None,
#         description="The estimated time remaining for processing the records in seconds",
#     )
#     records: SerializeAsAny[list[MetricResult]] = Field(
#         default_factory=list, description="The records of the profile results"
#     )
#     errors_by_type: list[ErrorDetailsCount] = Field(
#         default_factory=list,
#         description="A list of the unique error details and their counts",
#     )
#     is_complete: bool = Field(
#         default=False,
#         description="Whether the profile run is complete",
#     )
#     credit_phase: CreditPhase = Field(
#         default=CreditPhase.UNKNOWN,
#         description="The type of credit phase (either warmup or profiling)",
#     )

#     @property
#     def steady_state_completed(self) -> int:
#         """Calculate the number of requests completed during steady-state (after ramp-up)."""
#         return max(0, self.requests_completed - self.ramp_up_completed)

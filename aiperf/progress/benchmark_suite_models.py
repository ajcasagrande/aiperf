# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


# from aiperf.progress.progress_models import ProfileProgress


# class BenchmarkSuiteProgress(AIPerfBaseModel, ABC):
#     """State of the suite progress."""

#     suite_type: BenchmarkSuiteType = Field(
#         default=BenchmarkSuiteType.SINGLE_PROFILE,
#         description="The type of suite. Default is SINGLE_PROFILE.",
#     )
#     suite_completion_trigger: BenchmarkSuiteCompletionTrigger = Field(
#         default=BenchmarkSuiteCompletionTrigger.COMPLETED_PROFILES,
#         description="The trigger of suite completion",
#     )
#     start_time_ns: int | None = Field(
#         default=None,
#         description="The overall start time of the suite in nanoseconds. If it has not been started, this will be None.",
#     )
#     end_time_ns: int | None = Field(
#         default=None,
#         description="The overall end time of the suite in nanoseconds. If it has not been completed, this will be None.",
#     )
#     was_cancelled: bool = Field(
#         default=False,
#         description="Whether the suite was cancelled early",
#     )

#     # @property
#     # def current_sweep(self) -> SweepProgress | None:
#     #     if not isinstance(self, SweepSuiteProgress) or self.current_sweep_idx is None:
#     #         return None
#     #     return self.sweeps[self.current_sweep_idx]

#     @property
#     def current_profile(self) -> ProfileProgress | None:
#         if isinstance(self, ProfileSuiteProgress):
#             if self.current_profile_idx is None or self.current_profile_idx >= len(
#                 self.profiles
#             ):
#                 return None
#             return self.profiles[self.current_profile_idx]

#         # elif isinstance(self, SweepSuiteProgress):
#         #     if self.current_sweep is None:
#         #         return None
#         #     return self.current_sweep.current_profile

#         return None

#     @abstractmethod
#     def next_profile(self) -> ProfileProgress | None: ...


# class ProfileSuiteProgress(BenchmarkSuiteProgress):
#     """State of a profile based suite with 1 or more profile runs."""

#     profiles: list[ProfileProgress] = Field(
#         default_factory=list, description="The state of the profiles in the suite"
#     )
#     total_profiles: int = Field(default=0, description="The total number of profiles")
#     completed_profiles: int = Field(
#         default=0, description="The number of completed profiles"
#     )
#     current_profile_idx: int | None = Field(
#         default=None,
#         description="The index of the current profile run. If it has not been started, this will be None.",
#     )

#     def next_profile(self) -> ProfileProgress | None:
#         if self.current_profile_idx is None:
#             self.current_profile_idx = 0
#         else:
#             self.current_profile_idx += 1

#         if self.current_profile_idx >= len(self.profiles):
#             return None

#         return self.profiles[self.current_profile_idx]


# class SweepSuiteProgress(BenchmarkSuiteProgress):
#     """State of a sweep based suite with 1 or more sweep runs."""

#     sweeps: list[SweepProgress] = Field(
#         default_factory=list, description="The state of the sweeps in the suite"
#     )
#     total_sweeps: int = Field(default=0, description="The total number of sweeps")
#     completed_sweeps: int = Field(
#         default=0, description="The number of completed sweeps"
#     )
#     current_sweep_idx: int | None = Field(
#         default=None,
#         description="The index of the current sweep. If it has not been started, this will be None.",
#     )

#     def next_profile(self) -> ProfileProgress | None:
#         """Get the next profile to run.

#         Returns:
#             The next profile to run, or None if there are no more profiles to run.
#         """
#         if self.current_sweep is None or self.current_sweep.current_profile_idx is None:
#             next_sweep = self.next_sweep()
#             if next_sweep is None:
#                 return None
#             return next_sweep.next_profile()

#         # Try to get the next profile in the current sweep
#         next_profile = self.current_sweep.next_profile()
#         if next_profile is not None:
#             return next_profile

#         # If no more profiles in current sweep, move to next sweep
#         next_sweep = self.next_sweep()
#         if next_sweep is None:
#             return None
#         return next_sweep.next_profile()

#     def next_sweep(self) -> SweepProgress | None:
#         """Get the next sweep to run.

#         Returns:
#             The next sweep to run, or None if there are no more sweeps to run.
#         """
#         if self.current_sweep_idx is None:
#             self.current_sweep_idx = 0
#             return self.sweeps[0]
#         if self.current_sweep_idx >= len(self.sweeps) - 1:
#             return None
#         self.current_sweep_idx += 1
#         return self.sweeps[self.current_sweep_idx]

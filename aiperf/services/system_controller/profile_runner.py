# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
import time
from typing import TYPE_CHECKING

from aiperf.common.enums import (
    BenchmarkSuiteType,
    CommandType,
    SystemState,
)
from aiperf.progress.progress_tracker import BenchmarkSuiteProgress, ProfileRunProgress

if TYPE_CHECKING:
    from aiperf.services.system_controller.system_controller import SystemController


class ProfileRunner:
    """
    A class that manages the lifecycle of profile runs.
    """

    def __init__(
        self,
        controller: "SystemController",
    ):
        self.controller = controller
        self.tracker = self.controller.progress_tracker
        self.logger = logging.getLogger(self.__class__.__name__)
        self.was_cancelled = False

    async def run(self):
        self.controller._system_state = SystemState.PROFILING

        if self.tracker.suite is None:
            self.tracker.suite = BenchmarkSuiteProgress(
                type=BenchmarkSuiteType.SINGLE_PROFILE,
                profile_runs=[
                    ProfileRunProgress(
                        profile_id="0",
                        start_ns=time.time_ns(),
                    )
                ],
            )

        # Start the first profile
        self.tracker.suite.current_profile_run = self.tracker.suite.profile_runs[0]
        self.tracker.suite.current_profile_run.start_ns = time.time_ns()

        try:
            await self.controller.send_command_to_service(
                target_service_id=None,
                command=CommandType.PROFILE_START,
            )
        except Exception as e:
            self.logger.warning("Failed to start services: %s", e)
            # TODO: should we have some sort of retries?
            # raise self._service_error("Failed to start service") from e

    @property
    def is_complete(self) -> bool:
        return (
            self.tracker.current_profile_run is not None
            and self.tracker.current_profile_run.is_complete
        )

    async def profile_completed(self) -> None:
        if self.tracker.current_profile_run is None:
            self.logger.error("No current profile to complete")
            return

        self.tracker.current_profile_run.end_ns = time.time_ns()
        # TODO: Better way to track this?
        # self.tracker.current_profile_run.is_complete = True

        # Start the next profile
        # if self.tracker.suite is None or self.tracker.suite.current_profile_run is None:
        #     self.logger.info("All profiles completed")
        #     return

        # self.logger.info("Starting next profile")
        # self.tracker.suite.current_profile_run = self.tracker.suite.profile_runs[1]
        # self.tracker.suite.current_profile_run.start_ns = time.time_ns()

    async def cancel_profile(self) -> None:
        self.was_cancelled = True
        if self.tracker.current_profile_run is None:
            self.logger.error("No current profile to cancel")
            self.controller.stop_event.set()
            return

        # Check if active_credit_phase is None (profile hasn't started yet)
        if self.tracker.active_credit_phase is None:
            self.logger.warning(
                "Profile cancellation requested but no active credit phase found"
            )
            self.controller.stop_event.set()
            return

        # Check if the active phase exists in the phases dict
        if (
            self.tracker.active_credit_phase
            not in self.tracker.current_profile_run.phases
        ):
            self.logger.warning(
                "Active credit phase %s not found in phases dict",
                self.tracker.active_credit_phase,
            )
            self.controller.stop_event.set()
            return

        self.tracker.current_profile_run.was_cancelled = True
        self.controller.stop_event.set()

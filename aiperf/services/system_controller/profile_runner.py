# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
import time
from typing import TYPE_CHECKING

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import (
    BenchmarkSuiteType,
    CommandType,
    ServiceState,
    SystemState,
)
from aiperf.common.progress_models import ProfileProgress, ProfileSuiteProgress

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
        self.logger = logging.getLogger(__name__)
        self.was_cancelled = False

    async def run(self):
        self.controller._system_state = SystemState.PROFILING

        if self.tracker.suite is None:
            self.tracker.suite = ProfileSuiteProgress(
                suite_type=BenchmarkSuiteType.SINGLE_PROFILE,
                start_time_ns=time.time_ns(),
                profiles=[
                    ProfileProgress(
                        profile_id="0",
                        total_expected_requests=0,
                    )
                ],
                total_profiles=1,
            )

        # Start the first profile
        self.tracker.suite.next_profile()

        self.logger.debug("Starting services")
        for service_info in self.controller.service_manager.service_id_map.values():
            self.logger.debug("Starting service: %s", service_info.service_id)
            if service_info.state == ServiceState.READY:
                try:
                    await self.controller.send_command_to_service(
                        target_service_id=service_info.service_id,
                        command=CommandType.PROFILE_START,
                    )
                    self.logger.debug("Started service: %s", service_info.service_id)

                except Exception as e:
                    self.logger.warning("Failed to start service: %s", e)
                    # Continue to the next service
                    # TODO: should we have some sort of retries?
                    continue

    @property
    def is_complete(self) -> bool:
        return (
            self.tracker.current_profile is not None
            and self.tracker.current_profile.is_complete
        )

    async def profile_completed(self) -> None:
        if self.tracker.current_profile is None:
            self.logger.error("No current profile to complete")
            return

        self.tracker.current_profile.end_time_ns = time.time_ns()
        self.tracker.current_profile.is_complete = True
        if self.tracker.current_profile.start_time_ns is not None:
            self.tracker.current_profile.elapsed_time = (
                self.tracker.current_profile.end_time_ns
                - self.tracker.current_profile.start_time_ns
            ) / NANOS_PER_SECOND

        if self.tracker.suite is None or self.tracker.suite.next_profile() is None:
            self.logger.info("All profiles completed")
            return

        self.logger.info("Starting next profile")

    async def cancel_profile(self) -> None:
        self.was_cancelled = True
        if self.tracker.current_profile is None:
            self.logger.error("No current profile to cancel")
            self.controller.stop_event.set()
            return

        self.tracker.current_profile.was_cancelled = True
        self.tracker.current_profile.end_time_ns = time.time_ns()
        self.tracker.current_profile.is_complete = True
        self.controller.stop_event.set()

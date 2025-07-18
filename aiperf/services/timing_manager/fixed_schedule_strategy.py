# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import time
from collections import defaultdict

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import CreditPhase, TimingMode
from aiperf.common.exceptions import InvalidStateError
from aiperf.common.messages import CreditReturnMessage
from aiperf.common.mixins import AsyncTaskManagerMixin
from aiperf.common.models.progress_models import CreditPhaseStats
from aiperf.services.timing_manager.config import TimingManagerConfig
from aiperf.services.timing_manager.credit_issuing_strategy import (
    CreditIssuingStrategy,
    CreditIssuingStrategyFactory,
    CreditManagerProtocol,
)


@CreditIssuingStrategyFactory.register(TimingMode.FIXED_SCHEDULE)
class FixedScheduleStrategy(CreditIssuingStrategy, AsyncTaskManagerMixin):
    """
    Class for fixed schedule credit issuing strategy.
    """

    def __init__(
        self,
        config: TimingManagerConfig,
        credit_manager: CreditManagerProtocol,
        schedule: list[tuple[int, str]],
    ):
        super().__init__(config=config, credit_manager=credit_manager)

        self._schedule: list[tuple[int, str]] = schedule

        # Create a profiling phase for progress tracking
        self.active_phase = CreditPhaseStats(
            type=CreditPhase.PROFILING,
            start_ns=time.time_ns(),
            total_expected_requests=len(schedule),
            sent=0,
            completed=0,
        )

    async def start(self) -> None:
        if not self._schedule:
            raise InvalidStateError("No schedule loaded, no credits will be dropped")

        start_time_ns = time.time_ns()
        self.active_phase.start_ns = start_time_ns
        # In fixed schedule mode, measurement starts immediately
        self.active_phase.measurement_start_ns = start_time_ns

        # Start progress reporting
        self.execute_async(self._progress_report_loop())

        timestamp_groups = defaultdict(list)

        for timestamp, conversation_id in self._schedule:
            timestamp_groups[timestamp].append((timestamp, conversation_id))

        schedule_unique_sorted = sorted(timestamp_groups.keys())

        for unique_timestamp in schedule_unique_sorted:
            wait_duration_ns = max(0, start_time_ns + unique_timestamp - time.time_ns())
            wait_duration_sec = wait_duration_ns / NANOS_PER_SECOND

            if wait_duration_sec > 0:
                await asyncio.sleep(wait_duration_sec)

            for _, conversation_id in timestamp_groups[unique_timestamp]:
                self.execute_async(
                    self.credit_manager.drop_credit(
                        credit_phase=CreditPhase.PROFILING,
                        conversation_id=conversation_id,
                        credit_drop_ns=None,
                    )
                )
                self.active_phase.sent += 1

        self.logger.info("Completed all scheduled credit drops")
        # Wait for all credits to be returned
        await self.active_phase.completed_event.wait()  # TODO: Remove this

    async def _on_credit_return(self, message: CreditReturnMessage) -> None:
        """Process a credit return message."""
        self.active_phase.completed += 1

        if self.active_phase.completed >= self.active_phase.total_expected_requests:
            self.active_phase.end_ns = time.time_ns()
            self.execute_async(
                self.credit_manager.publish_credits_complete(
                    self.active_phase.type, False
                )
            )
            self.active_phase.completed_event.set()  # TODO: Remove this

    async def _report_progress(self) -> None:
        """Report the progress of the active phase."""
        try:
            await self.credit_manager.publish_progress(self.active_phase)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.exception("TM: Error publishing progress: %s", e)

    async def _progress_report_loop(self) -> None:
        """Report the progress at a fixed interval."""
        while not self.active_phase.completed_event.is_set():  # TODO: Remove this
            try:
                await self._report_progress()
            except asyncio.CancelledError:
                self.logger.debug("TM: Progress reporting loop cancelled")
                return

            await asyncio.sleep(1)  # TODO: Make this configurable

        self.logger.debug("TM: All credits completed, stopping progress reporting loop")

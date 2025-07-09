# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging
import random
import time

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import CreditPhase
from aiperf.common.exceptions import InvalidStateError
from aiperf.common.messages import CreditReturnMessage
from aiperf.common.mixins import AsyncTaskManagerMixin
from aiperf.progress.progress_models import CreditPhaseStats
from aiperf.services.timing_manager.config import TimingManagerConfig
from aiperf.services.timing_manager.credit_issuing_strategy import (
    CreditIssuingStrategy,
    CreditManagerProtocol,
)


class ConcurrencyStrategy(CreditIssuingStrategy, AsyncTaskManagerMixin):
    """Class for concurrency credit issuing strategy."""

    def __init__(
        self, config: TimingManagerConfig, credit_manager: CreditManagerProtocol
    ):
        super().__init__(config=config, credit_manager=credit_manager)
        self.logger = logging.getLogger(__class__.__name__)

        if not config.request_count or config.request_count < 1:
            # TODO: Add support for alternate completion triggers vs request count (eg. time based)
            raise InvalidStateError("Request count must be at least 1")

        # The phases to run, in order
        self.phases: list[CreditPhaseStats] = []

        # Add the warmup phase if applicable
        if config.warmup_request_count > 0:
            self.phases.append(
                CreditPhaseStats(
                    type=CreditPhase.WARMUP, total=config.warmup_request_count
                )
            )

        # Add the ramp-up phase if applicable
        if config.concurrency_ramp_up_time and config.concurrency_ramp_up_time > 0:
            self.phases.append(
                CreditPhaseStats(
                    type=CreditPhase.RAMP_UP,
                    total=None,
                    expected_duration_ns=int(
                        config.concurrency_ramp_up_time * NANOS_PER_SECOND
                    ),
                )
            )

        # Add the steady-state phase
        self.phases.append(
            CreditPhaseStats(type=CreditPhase.STEADY_STATE, total=config.request_count)
        )

        # Link the phase stats by phase type for easy access
        self.phase_stats: dict[CreditPhase, CreditPhaseStats] = {
            phase.type: phase for phase in self.phases
        }
        self.active_phase: CreditPhaseStats = self.phases[0]

        # if the concurrency is larger than the total credits, it does not matter
        # as it is simply an upper bound that will never be reached
        self._concurrency = config.concurrency
        self._concurrency_ramp_up_time = config.concurrency_ramp_up_time
        self._semaphore = asyncio.Semaphore(value=self._concurrency)

        self.logger.info(
            "TM: Concurrency Strategy initialized with %d phases: %s",
            len(self.phases),
            self.phases,
        )

    async def start(self) -> None:
        """Start the credit issuing strategy. This will launch the progress reporting loop, the
        warmup phase (if applicable), and the profiling phase, all in the background."""

        # Start the progress reporting loop in the background
        self.execute_async(self._progress_report_loop())

        # Execute the phases in the background
        self.execute_async(self._execute_phases())

    async def _execute_time_based_phase(self, phase: CreditPhaseStats) -> None:
        """Execute a time-based phase of credit issuing."""
        if not phase.expected_duration_ns or phase.expected_duration_ns <= 0:
            raise InvalidStateError("Expected duration must be set and positive")

        while time.time_ns() - phase.start_ns < phase.expected_duration_ns:
            await self._semaphore.acquire()
            if time.time_ns() - phase.start_ns >= phase.expected_duration_ns:
                # If the time has expired, do not send the credit
                return
            self.execute_async(
                self.credit_manager.drop_credit(
                    credit_phase=phase.type,
                    conversation_id=None,
                    credit_drop_ns=None,
                )
            )
            phase.sent += 1

    async def _execute_request_count_based_phase(self, phase: CreditPhaseStats) -> None:
        """Execute a request count-based phase of credit issuing."""
        if not phase.total or phase.total <= 0:
            raise InvalidStateError("Total must be set and positive")

        while phase.sent < phase.total:
            await self._semaphore.acquire()
            self.execute_async(
                self.credit_manager.drop_credit(
                    credit_phase=phase.type,
                    conversation_id=None,
                    credit_drop_ns=None,
                )
            )
            phase.sent += 1

    async def _execute_phases(self) -> None:
        """Execute the phases in the background."""
        for phase in self.phases:
            phase.start_ns = time.time_ns()
            self.execute_async(self.credit_manager.publish_phase_start(phase))

            if phase.type == CreditPhase.RAMP_UP:
                await self._execute_with_ramp_up(phase)
            elif phase.expected_duration_ns:
                await self._execute_time_based_phase(phase)
            elif phase.total:
                await self._execute_request_count_based_phase(phase)
            else:
                raise InvalidStateError(
                    "Phase must have either total or expected_duration_ns set"
                )

            phase.sent_end_ns = time.time_ns()

    async def _execute_with_ramp_up(self, phase: CreditPhaseStats) -> None:
        """Execute with Poisson-based ramp-up to target concurrency."""

        if not self._concurrency_ramp_up_time or self._concurrency_ramp_up_time <= 0:
            raise InvalidStateError("Ramp-up time must be set and positive")

        random_generator = (
            random.Random(self.config.random_seed)
            if self.config.random_seed
            else random.Random()
        )

        # Ramp-up phase - gradually reach target concurrency
        ramp_up_requests = self._concurrency
        self.logger.info(
            "TM: Starting ramp-up phase: %s requests over %s seconds",
            ramp_up_requests,
            self._concurrency_ramp_up_time,
        )

        ramp_up_start_time = time.time()

        # Send initial requests using Poisson timing during ramp-up
        for i in range(ramp_up_requests):
            if phase.sent >= self._concurrency:
                break

            await self._semaphore.acquire()

            # Calculate progress through ramp-up (0 to 1)
            progress = (i + 1) / ramp_up_requests

            # Use time-varying Poisson process - rate increases linearly
            # Target: reach full concurrency by end of ramp-up time
            target_rate = (ramp_up_requests / self._concurrency_ramp_up_time) * progress

            if target_rate > 0 and i > 0:  # Skip delay for first request
                # Exponential inter-arrival time for Poisson process
                wait_time = random_generator.expovariate(target_rate)

                # Don't exceed total ramp-up time
                elapsed_time = time.time() - ramp_up_start_time
                remaining_time = self._concurrency_ramp_up_time - elapsed_time

                if wait_time > remaining_time and remaining_time > 0:
                    wait_time = remaining_time

                if wait_time > 0:
                    await asyncio.sleep(wait_time)

            self.execute_async(
                self.credit_manager.drop_credit(
                    credit_phase=phase.type,
                    conversation_id=None,
                    credit_drop_ns=None,
                )
            )
            phase.sent += 1

    async def on_credit_return(self, message: CreditReturnMessage) -> None:
        """Process a credit return message."""

        self._semaphore.release()
        phase_stats = self.phase_stats[message.credit_phase]
        phase_stats.completed += 1

        if phase_stats.completed >= phase_stats.total:
            phase_stats.end_ns = time.time_ns()
            self.execute_async(
                self.credit_manager.publish_credits_complete(phase_stats, False)
            )
            self.execute_async(self.credit_manager.publish_phase_complete(phase_stats))

    async def _report_progress(self) -> None:
        """Report the progress of the active phase."""
        try:
            await self.credit_manager.publish_progress(self.phase_stats)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.error("TM: Error publishing progress: %s", e)

    async def _progress_report_loop(self) -> None:
        """Report the progress at a fixed interval."""
        self.logger.debug("TM: Starting progress reporting loop")
        while not self.all_phases_complete():
            try:
                await self._report_progress()
            except asyncio.CancelledError:
                self.logger.debug("TM: Progress reporting loop cancelled")
                return

            await asyncio.sleep(1)  # TODO: Make this configurable

        self.logger.debug(
            "TM: All credits completed, stopping progress reporting loop",
        )

    def all_phases_complete(self) -> bool:
        """Check if all phases are complete."""
        return all(phase.is_complete for phase in self.phases)

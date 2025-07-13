# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging
import random
import time

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.credit_models import CreditPhaseStats
from aiperf.common.enums import CreditPhase
from aiperf.common.exceptions import InvalidStateError
from aiperf.common.messages import CreditReturnMessage
from aiperf.common.mixins.async_task_manager import AsyncTaskManagerMixin
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
        self.logger = logging.getLogger(self.__class__.__name__)

        if not config.request_count or config.request_count < 1:
            # TODO: Add support for alternate completion triggers vs request count (eg. time based)
            raise InvalidStateError("Request count must be at least 1")

        # if the concurrency is larger than the total credits, it does not matter
        # as it is simply an upper bound that will never be reached
        self._concurrency = config.concurrency
        self._ramp_up_time = config.concurrency_ramp_up_time
        self._semaphore = asyncio.Semaphore(value=self._concurrency)

        self._setup_phases()

    def _setup_phases(self) -> None:
        """Setup the phases for the strategy."""
        # Add the warmup phase if applicable
        if self.config.warmup_request_count > 0:
            self.phases.append(
                CreditPhaseStats(
                    type=CreditPhase.WARMUP, total=self.config.warmup_request_count
                )
            )

        # Add the ramp-up phase if applicable
        if (
            self.config.concurrency_ramp_up_time
            and self.config.concurrency_ramp_up_time > 0
        ):
            self.phases.append(
                CreditPhaseStats(
                    type=CreditPhase.RAMP_UP,
                    total=None,
                    expected_duration_ns=int(
                        self.config.concurrency_ramp_up_time * NANOS_PER_SECOND
                    ),
                )
            )

        # Add the steady-state phase
        self.phases.append(
            CreditPhaseStats(
                type=CreditPhase.STEADY_STATE, total=self.config.request_count
            )
        )

        # Link the phase stats by phase type for easy access
        self.phase_stats: dict[CreditPhase, CreditPhaseStats] = {
            phase.type: phase for phase in self.phases
        }
        self.active_phase: CreditPhaseStats = self.phases[0]

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
        start_ns: int = phase.start_ns  # type: ignore[assignment]
        expected_duration_ns: int = phase.expected_duration_ns  # type: ignore[assignment]

        while time.time_ns() - start_ns < expected_duration_ns:
            await self._semaphore.acquire()

            if time.time_ns() - start_ns >= expected_duration_ns:
                # If the time has expired while we were waiting for the semaphore,
                # do not send the credit
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
        total: int = phase.total  # type: ignore[assignment]

        while phase.sent < total:
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
        for phase in self.phases:
            phase.start_ns = time.time_ns()
            self.execute_async(self.credit_manager.publish_phase_start(phase))

            if phase.type == CreditPhase.RAMP_UP:
                await self._execute_with_ramp_up(phase)
            elif phase.is_time_based:
                await self._execute_time_based_phase(phase)
            elif phase.total and phase.total > 0:
                await self._execute_request_count_based_phase(phase)
            else:
                raise InvalidStateError(
                    "Phase must have either a valid total or expected_duration_ns set"
                )

            # We have sent all the credits for this phase. We must continue to the next
            # phase even though not all the credits have been returned. This is because
            # we do not want a gap in the credit issuing.
            phase.sent_end_ns = time.time_ns()
            self.execute_async(
                self.credit_manager.publish_phase_sending_complete(phase)
            )

    # TODO: This is still very experimental, and needs to be improved
    async def _execute_with_ramp_up(self, phase: CreditPhaseStats) -> None:
        """Execute with Poisson-based ramp-up to target concurrency."""

        if not self._ramp_up_time or self._ramp_up_time <= 0:
            raise InvalidStateError("Ramp-up time must be set and positive")

        random_generator = (
            random.Random(self.config.random_seed)
            if self.config.random_seed
            else random.Random()
        )

        # ramp-up phase - gradually reach target concurrency
        ramp_up_requests = self._concurrency
        self.logger.info(
            "TM: Starting ramp-up phase: %s requests over %s seconds",
            ramp_up_requests,
            self._ramp_up_time,
        )

        ramp_up_start_time = time.time()

        # send initial requests using Poisson timing during ramp-up
        for i in range(ramp_up_requests):
            if phase.sent >= self._concurrency:
                break

            await self._semaphore.acquire()

            # calculate progress through ramp-up (0 to 1)
            progress = (i + 1) / ramp_up_requests

            # time-varying Poisson process - rate increases linearly
            # target: reach full concurrency by end of ramp-up time
            target_rate = (ramp_up_requests / self._ramp_up_time) * progress

            if target_rate > 0 and i > 0:  # skip delay for first request
                # exponential inter-arrival time for Poisson process
                wait_time = random_generator.expovariate(target_rate)

                # don't exceed total ramp-up time
                wait_time = min(
                    wait_time,
                    self._ramp_up_time - (time.time() - ramp_up_start_time),
                )

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

        if (
            # If we have sent all the credits, check if this is the last one to be returned
            phase_stats.is_sending_complete
            and phase_stats.completed >= phase_stats.total  # type: ignore[operator]
        ):
            phase_stats.end_ns = time.time_ns()
            self.logger.info("TM: Phase completed: %s", phase_stats)

            self.execute_async(self.credit_manager.publish_phase_complete(phase_stats))

            if self.all_phases_complete():
                self.execute_async(
                    self.credit_manager.publish_credits_complete(cancelled=False)
                )

    async def _progress_report_loop(self) -> None:
        """Report the progress at a fixed interval."""
        self.logger.debug("TM: Starting progress reporting loop")
        while not self.all_phases_complete():
            try:
                await self.credit_manager.publish_progress(self.phase_stats)
            except asyncio.CancelledError:
                self.logger.debug("TM: Progress reporting loop cancelled")
                return

            await asyncio.sleep(1)  # TODO: Make this configurable

        self.logger.debug(
            "TM: All credits completed, stopping progress reporting loop",
        )

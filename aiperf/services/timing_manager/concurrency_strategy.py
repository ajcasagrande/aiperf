# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import random
import time

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.credit_models import CreditPhaseConfig, CreditPhaseStats
from aiperf.common.enums import CreditPhase
from aiperf.common.exceptions import InvalidStateError
from aiperf.common.messages import CreditReturnMessage
from aiperf.common.mixins import AIPerfLoggerMixin, AsyncTaskManagerMixin
from aiperf.services.timing_manager.config import TimingManagerConfig
from aiperf.services.timing_manager.credit_issuing_strategy import (
    CreditIssuingStrategy,
    CreditManagerProtocol,
)


class ConcurrencyStrategy(
    CreditIssuingStrategy, AsyncTaskManagerMixin, AIPerfLoggerMixin
):
    """Class for concurrency credit issuing strategy."""

    def __init__(
        self, config: TimingManagerConfig, credit_manager: CreditManagerProtocol
    ):
        super().__init__(config=config, credit_manager=credit_manager)

        if not config.request_count or config.request_count < 1:
            # TODO: Add support for alternate completion triggers vs request count (eg. time based)
            raise InvalidStateError("Request count must be at least 1")

        # if the concurrency is larger than the total number of requests, it does not matter
        # as it is simply an upper bound that will never be reached
        self._concurrency = config.concurrency
        self._ramp_up_time_seconds = config.concurrency_ramp_up_time_seconds
        self._semaphore = asyncio.Semaphore(value=self._concurrency)

        # The phases to run including their configuration, in order of execution.
        self.ordered_phase_configs: list[CreditPhaseConfig] = []

        self._setup_phases()

    def _setup_phases(self) -> None:
        """Setup the phases for the strategy."""
        # Add the warmup phase if applicable
        if self.config.warmup_request_count > 0:
            self.ordered_phase_configs.append(
                CreditPhaseConfig(
                    type=CreditPhase.WARMUP,
                    total_expected_requests=self.config.warmup_request_count,
                )
            )

        # Add the ramp-up phase if applicable
        if (
            self.config.concurrency_ramp_up_time_seconds
            and self.config.concurrency_ramp_up_time_seconds > 0
        ):
            self.ordered_phase_configs.append(
                CreditPhaseConfig(
                    type=CreditPhase.WARMUP,
                    expected_duration_ns=int(
                        self.config.concurrency_ramp_up_time_seconds * NANOS_PER_SECOND
                    ),
                )
            )

        # Add the profiling phase
        self.ordered_phase_configs.append(
            CreditPhaseConfig(
                type=CreditPhase.PROFILING,
                total_expected_requests=self.config.request_count,
            )
        )

        self.info(
            lambda: f"Concurrency Strategy initialized with {len(self.ordered_phase_configs)} phases: {self.ordered_phase_configs}"
        )

    async def _execute_phases(self) -> None:
        for phase_config in self.ordered_phase_configs:
            if not phase_config.is_valid:
                raise InvalidStateError(
                    f"Phase {phase_config.type} is not valid. It must have either a valid total_expected_requests or expected_duration_ns set"
                )

            phase_stats = CreditPhaseStats(
                type=phase_config.type,
                start_ns=time.time_ns(),
                # Only one of these will be set, this was validated above
                total_expected_requests=phase_config.total_expected_requests,
                expected_duration_ns=phase_config.expected_duration_ns,
            )
            self.execute_async(
                self.credit_manager.publish_phase_start(
                    phase_config.type,
                    phase_stats.start_ns,  # type: ignore - we set it above
                    phase_config.total_expected_requests,
                    phase_config.expected_duration_ns,
                )
            )

            if phase_config.is_time_based:
                await self._execute_time_based_phase(phase_stats)
            elif phase_config.is_request_count_based:
                await self._execute_request_count_based_phase(phase_stats)
            else:
                raise InvalidStateError(
                    "Phase must have either a valid total or expected_duration_ns set"
                )

            # We have sent all the credits for this phase. We must continue to the next
            # phase even though not all the credits have been returned. This is because
            # we do not want a gap in the credit issuing.
            self.execute_async(
                self.credit_manager.publish_phase_sending_complete(
                    phase_config.type, time.time_ns()
                )
            )

    async def _execute_time_based_phase(self, phase: CreditPhaseStats) -> None:
        start_ns: int = phase.start_ns  # type: ignore[assignment]
        expected_duration_ns: int = phase.expected_duration_ns  # type: ignore[assignment]

        while time.time_ns() - start_ns < expected_duration_ns:
            await self._semaphore.acquire()

            if time.time_ns() - start_ns >= expected_duration_ns:
                # If the time has expired while we were waiting for the semaphore,
                # do not send the credit. This is to be expected.
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
        total: int = phase.total_expected_requests  # type: ignore[assignment]

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

    # TODO: This is still very experimental, and needs to be improved
    async def _execute_with_ramp_up(self, phase: CreditPhaseStats) -> None:
        """Execute with Poisson-based ramp-up to target concurrency."""

        if not self._ramp_up_time_seconds or self._ramp_up_time_seconds <= 0:
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
            self._ramp_up_time_seconds,
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
            target_rate = (ramp_up_requests / self._ramp_up_time_seconds) * progress

            if target_rate > 0 and i > 0:  # skip delay for first request
                # exponential inter-arrival time for Poisson process
                wait_time = random_generator.expovariate(target_rate)

                # don't exceed total ramp-up time
                wait_time = min(
                    wait_time,
                    self._ramp_up_time_seconds - (time.time() - ramp_up_start_time),
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

        # Release the semaphore, then call the superclass to handle the credit return
        self._semaphore.release()
        self.trace(lambda: f"TM: Released semaphore: {self._semaphore}")
        await super().on_credit_return(message)

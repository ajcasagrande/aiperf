# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import random
import time

from aiperf.common.credit_models import CreditPhaseStats
from aiperf.common.enums import CreditPhase, RequestRateMode
from aiperf.common.exceptions import InvalidStateError
from aiperf.common.mixins.async_task_manager import AsyncTaskManagerMixin
from aiperf.services.timing_manager.config import TimingManagerConfig
from aiperf.services.timing_manager.credit_issuing_strategy import (
    CreditIssuingStrategy,
    CreditManagerProtocol,
)


class RequestRateStrategy(CreditIssuingStrategy, AsyncTaskManagerMixin):
    """
    Strategy for issuing credits based on a specified request rate.

    Supports two modes:
    - CONSTANT: Issues credits at a constant rate with fixed intervals
    - POISSON: Issues credits using a Poisson process with exponentially distributed intervals
    """

    def __init__(
        self, config: TimingManagerConfig, credit_manager: CreditManagerProtocol
    ):
        super().__init__(config=config, credit_manager=credit_manager)

        if config.request_rate is None:
            raise InvalidStateError("Request rate is not set")
        if config.request_count < 1:
            raise InvalidStateError("Request count must be at least 1")

        self._request_rate = config.request_rate
        self._request_rate_mode = config.request_rate_mode

        # Initialize random number generator for reproducibility
        self._random = (
            random.Random(config.random_seed) if config.random_seed else random.Random()
        )

        self._setup_phases()

    def _setup_phases(self) -> None:
        """Setup the phases for the strategy."""
        # Add the warmup phase if applicable
        if self.config.warmup_request_count > 0:
            self.phases.append(CreditPhase.WARMUP)
            self.phase_stats[CreditPhase.WARMUP] = CreditPhaseStats(
                type=CreditPhase.WARMUP, total_requests=self.config.warmup_request_count
            )

        # Add the steady-state phase
        self.phases.append(CreditPhase.PROFILING)
        self.phase_stats[CreditPhase.PROFILING] = CreditPhaseStats(
            type=CreditPhase.PROFILING, total_requests=self.config.request_count
        )

        self.active_phase_idx = 0
        self.active_phase: CreditPhaseStats = self.phase_stats[
            self.phases[self.active_phase_idx]
        ]

        self.info(
            lambda: f"TM: Request Rate Strategy initialized with {len(self.phases)} phases: {self.phases}"
        )

    async def _execute_phases(self) -> None:
        """Execute all phases sequentially."""
        for phase in self.phases:
            stats = CreditPhaseStats(
                type=phase,
                start_ns=time.time_ns(),
                total_requests=self.phase_stats[phase].total_requests,
                expected_duration_ns=self.phase_stats[phase].expected_duration_ns,
            )
            self.execute_async(
                self.credit_manager.publish_phase_start(
                    phase,
                    stats.start_ns,
                    stats.total_requests,
                    stats.expected_duration_ns,
                )
            )

            self.info(
                f"TM: Executing phase (total_credits={stats.total_requests}, request_rate={self._request_rate}, phase_type={phase}, start_time_ns={stats.start_ns})"
            )

            # Issue credit drops at the specified rate
            if self._request_rate_mode == RequestRateMode.CONSTANT:
                await self._execute_constant_rate(stats)
            elif self._request_rate_mode == RequestRateMode.POISSON:
                await self._execute_poisson_rate(stats)
            else:
                raise InvalidStateError(
                    f"Unsupported request rate mode: {self._request_rate_mode}"
                )

            # We have sent all the credits. we can continue to the next phase even though
            # not all the credits have been returned. This is because we do not want a
            # gap in the credit issuing.
            stats.sent_end_ns = time.time_ns()
            self.execute_async(
                self.credit_manager.publish_phase_sending_complete(
                    phase, stats.sent_end_ns
                )
            )

            self.debug(lambda phase=phase: f"TM: Sent all credits for phase {phase}")

    async def _execute_constant_rate(self, phase: CreditPhaseStats) -> None:
        """Execute credit drops at a constant rate."""
        if not phase.total_requests:
            raise InvalidStateError(
                "Phase total must be set for request count based phase"
            )

        # The effective time between each credit drop is the inverse of the request rate.
        period_sec = 1.0 / self._request_rate

        # We start by sending the first credit immediately.
        next_drop_at = time.perf_counter()

        while phase.sent < phase.total_requests:
            wait_sec = next_drop_at - time.perf_counter()
            if wait_sec > 0:
                await asyncio.sleep(wait_sec)

            self.execute_async(
                self.credit_manager.drop_credit(
                    credit_phase=phase.type,
                    conversation_id=None,
                    credit_drop_ns=None,
                )
            )
            phase.sent += 1

            # Instead of naively sleeping for a constant period_sec, we are scheduling the
            # next drop to happen at exactly (next_drop_at + period_sec). This ensures that
            # we do not slowly drift over time based on slight variances in the asyncio.sleep
            # or executing the credit drop task.
            next_drop_at += period_sec

    async def _execute_poisson_rate(self, phase: CreditPhaseStats) -> None:
        """Execute credit drops using Poisson distribution (exponential inter-arrival times).

        In a Poisson process with rate λ (requests per second), the inter-arrival times
        are exponentially distributed with parameter λ. This models realistic traffic
        patterns where requests arrive randomly but at a consistent average rate.
        """
        if not phase.total_requests:
            raise InvalidStateError(
                "Phase total must be set for request count based phase"
            )

        while phase.sent < phase.total_requests:
            # For Poisson process, inter-arrival times are exponentially distributed.
            # random.expovariate(lambd) generates exponentially distributed random numbers
            # where lambd is the rate parameter (requests per second)
            wait_duration_sec = self._random.expovariate(self._request_rate)

            if wait_duration_sec > 0:
                await asyncio.sleep(wait_duration_sec)

            self.execute_async(
                self.credit_manager.drop_credit(
                    credit_phase=phase.type,
                    conversation_id=None,
                    credit_drop_ns=None,
                )
            )
            phase.sent += 1

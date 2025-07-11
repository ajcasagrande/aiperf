# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging
import random
import time

from aiperf.common.credit_models import CreditPhaseStats
from aiperf.common.enums import CreditPhase, RequestRateMode
from aiperf.common.exceptions import InvalidStateError
from aiperf.common.messages import CreditReturnMessage
from aiperf.common.mixins import AsyncTaskManagerMixin
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
        self.logger = logging.getLogger(self.__class__.__name__)

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
            self.phases.append(
                CreditPhaseStats(
                    type=CreditPhase.WARMUP, total=self.config.warmup_request_count
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
            "TM: Request Rate Strategy initialized with %d phases: %s",
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

    async def _execute_phases(self) -> None:
        """Execute all phases sequentially."""
        for phase in self.phases:
            phase.start_ns = time.time_ns()
            self.active_phase = phase
            self.execute_async(self.credit_manager.publish_phase_start(phase))

            self.logger.info(
                "TM: Executing phase (total_credits=%s, request_rate=%s, phase_type=%s, start_time_ns=%s)",
                phase.total,
                self._request_rate,
                phase.type,
                phase.start_ns,
            )

            # Issue credit drops at the specified rate
            if self._request_rate_mode == RequestRateMode.CONSTANT:
                await self._execute_constant_rate(phase)
            elif self._request_rate_mode == RequestRateMode.POISSON:
                await self._execute_poisson_rate(phase)
            else:
                raise InvalidStateError(
                    f"Unsupported request rate mode: {self._request_rate_mode}"
                )

            # We have sent all the credits. we can continue to the next phase even though
            # not all the credits have been returned. This is because we do not want a
            # gap in the credit issuing.
            phase.sent_end_ns = time.time_ns()
            self.execute_async(
                self.credit_manager.publish_phase_sending_complete(phase)
            )

            self.logger.debug("TM: Sent all credits for phase %s", phase)

    async def _execute_constant_rate(self, phase: CreditPhaseStats) -> None:
        """Execute credit drops at a constant rate."""
        if not phase.total:
            raise InvalidStateError(
                "Phase total must be set for request count based phase"
            )

        # The effective time between each credit drop is the inverse of the request rate.
        period_sec = 1.0 / self._request_rate

        # We start by sending the first credit immediately.
        next_drop_at = time.perf_counter()

        while phase.sent < phase.total:
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
        if not phase.total:
            raise InvalidStateError(
                "Phase total must be set for request count based phase"
            )

        while phase.sent < phase.total:
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

    async def on_credit_return(self, message: CreditReturnMessage) -> None:
        """Process a credit return message."""
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

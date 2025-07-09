# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging
import random
import time

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import CreditPhase, RequestRateMode
from aiperf.common.exceptions import InvalidStateError
from aiperf.common.messages import CreditReturnMessage
from aiperf.common.mixins import AsyncTaskManagerMixin
from aiperf.progress.progress_models import CreditPhaseStats
from aiperf.services.timing_manager.config import TimingManagerConfig
from aiperf.services.timing_manager.credit_issuing_strategy import (
    CreditIssuingStrategy,
    CreditManagerProtocol,
)


class RequestRateStrategy(CreditIssuingStrategy, AsyncTaskManagerMixin):
    """
    Class for rate credit issuing strategy.

    Supports two modes:
    - CONSTANT: Issues credits at a constant rate with fixed intervals
    - POISSON: Issues credits using a Poisson process with exponentially distributed intervals
    """

    def __init__(
        self, config: TimingManagerConfig, credit_manager: CreditManagerProtocol
    ):
        super().__init__(config=config, credit_manager=credit_manager)
        self.logger = logging.getLogger(__class__.__name__)

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

        self.profiling = CreditPhaseStats(
            total=config.request_count, type=CreditPhase.STEADY_STATE
        )
        self.active_phase = self.profiling

        self.warmup = None
        if config.warmup_request_count > 0:
            self.warmup = CreditPhaseStats(
                total=config.warmup_request_count,
                type=CreditPhase.WARMUP,
            )
            self.active_phase = self.warmup

        self.logger.info(
            "TM: Request Rate Strategy initialized with total_credits=%s, request_rate=%s, request_rate_mode=%s, warmup_request_count=%s",
            self.active_phase.total,
            self._request_rate,
            self._request_rate_mode,
            config.warmup_request_count,
        )

    async def start(self) -> None:
        """Start the credit issuing strategy. This will launch the progress reporting loop, the
        warmup phase (if applicable), and the profiling phase, all in the background."""

        self.execute_async(self._progress_report_loop())
        if self.warmup:
            self.execute_async(self._execute_phase(self.warmup))
        self.execute_async(
            self._execute_phase(
                self.profiling, self.warmup.completed_event if self.warmup else None
            )
        )

    async def _execute_phase(
        self, phase: CreditPhaseStats, wait_for_event: asyncio.Event | None = None
    ) -> None:
        """Execute a phase of credit issuing. If a wait_for_event is provided,
        it will wait for the event to be set before executing the phase."""

        if wait_for_event is not None:
            self.logger.info("TM: Waiting for warmup to complete")
            await wait_for_event.wait()
            self.logger.info("TM: Warmup completed")

        self.active_phase = phase
        self.logger.info(
            "TM: Executing phase (total_credits=%s, request_rate=%s, phase_type=%s, start_time_ns=%s)",
            phase.total,
            self._request_rate,
            phase.type,
            phase.start_time_ns,
        )

        phase.start_time_ns = time.time_ns()
        # In rate mode, measurement starts immediately since there's no ramp-up
        phase.measurement_start_time_ns = phase.start_time_ns

        # Report the initial progress of the phase to ensure everything is in sync
        self.execute_async(self._report_progress())

        # Issue credit drops at the specified rate
        if self._request_rate_mode == RequestRateMode.CONSTANT:
            await self._execute_constant_rate(phase)
        elif self._request_rate_mode == RequestRateMode.POISSON:
            await self._execute_poisson_rate(phase)
        else:
            raise InvalidStateError(
                f"Unsupported request rate mode: {self._request_rate_mode}"
            )

        self.logger.debug("TM: Sent all credits for phase %s", phase)

    async def _execute_constant_rate(self, phase: CreditPhaseStats) -> None:
        """Execute credit drops at a constant rate."""
        period_sec = 1.0 / self._request_rate
        prev = time.perf_counter()

        while phase.sent < phase.total:
            self.execute_async(
                self.credit_manager.drop_credit(
                    credit_phase=phase.type,
                    conversation_id=None,
                    credit_drop_ns=None,
                )
            )
            phase.sent += 1

            now = time.perf_counter()
            wait_duration_sec = period_sec - (now - prev)
            if wait_duration_sec > 0:
                await asyncio.sleep(wait_duration_sec)
            prev = now

    async def _execute_poisson_rate(self, phase: CreditPhaseStats) -> None:
        """Execute credit drops using Poisson distribution (exponential inter-arrival times).

        In a Poisson process with rate λ (requests per second), the inter-arrival times
        are exponentially distributed with parameter λ. This models realistic traffic
        patterns where requests arrive randomly but at a consistent average rate.
        """
        while phase.sent < phase.total:
            # For Poisson process, inter-arrival times are exponentially distributed
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

    async def _report_progress(self) -> None:
        """Report the progress of the active phase."""
        try:
            await self.credit_manager.publish_progress(self.active_phase)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.error("TM: Error publishing progress: %s", e)

    async def _progress_report_loop(self) -> None:
        """Report the progress at a fixed interval."""
        while True:
            # Check if the profiling phase (final phase) is complete
            if self.profiling.completed_event.is_set():
                self.logger.debug(
                    "TM: All credits completed, stopping progress reporting loop"
                )
                break

            try:
                await self._report_progress()
            except asyncio.CancelledError:
                self.logger.debug("TM: Progress reporting loop cancelled")
                break

            await asyncio.sleep(1)  # TODO: Make this configurable

    async def on_credit_return(self, message: CreditReturnMessage) -> None:
        """Process a credit return message."""

        self.active_phase.completed += 1

        if self.logger.isEnabledFor(logging.DEBUG):
            # Use measurement start time and steady-state credits for rate calculation in debug logs
            measurement_start_ns = (
                self.active_phase.measurement_start_time_ns
                or self.active_phase.start_time_ns
            )
            steady_state_completed = self.active_phase.steady_state_completed_credits
            per_sec = (
                steady_state_completed
                / ((time.time_ns() - measurement_start_ns) / NANOS_PER_SECOND)
                if (time.time_ns() - measurement_start_ns) > 0
                else 0
            )
            self.logger.debug(
                "TM: Processing credit return: %s (total: %s/%s, steady-state: %s) (%.2f requests/s steady-state)",
                message,
                self.active_phase.completed,
                self.active_phase.total,
                steady_state_completed,
                per_sec,
            )

        if self.active_phase.completed >= self.active_phase.total:
            self.active_phase.end_time_ns = time.time_ns()
            self.execute_async(
                self.credit_manager.publish_credits_complete(
                    self.active_phase.type, False
                )
            )

            if self.logger.isEnabledFor(logging.DEBUG):
                # Use measurement start time and steady-state credits for final rate calculation in debug logs
                measurement_start_ns = (
                    self.active_phase.measurement_start_time_ns
                    or self.active_phase.start_time_ns
                )
                steady_state_completed = (
                    self.active_phase.steady_state_completed_credits
                )
                per_sec = (
                    steady_state_completed
                    / ((time.time_ns() - measurement_start_ns) / NANOS_PER_SECOND)
                    if (time.time_ns() - measurement_start_ns) > 0
                    else 0
                )
                self.logger.debug(
                    "TM: All credits completed, stopping credit drop task after %.2f seconds (%.2f steady-state requests/s)",
                    (time.time_ns() - self.active_phase.start_time_ns)
                    / NANOS_PER_SECOND,
                    per_sec,
                )

            self.active_phase.completed_event.set()

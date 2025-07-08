# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging
import time

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import CreditPhaseType
from aiperf.common.exceptions import InvalidStateError
from aiperf.common.messages import CreditReturnMessage
from aiperf.common.mixins import AsyncTaskManagerMixin
from aiperf.services.timing_manager.config import CreditPhase, TimingManagerConfig
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

        self.profiling = CreditPhase(
            total_credits=config.request_count, phase_type=CreditPhaseType.PROFILING
        )
        self.active_phase = self.profiling

        self.warmup = None
        if config.warmup_request_count > 0:
            self.warmup = CreditPhase(
                total_credits=config.warmup_request_count,
                phase_type=CreditPhaseType.WARMUP,
            )
            self.active_phase = self.warmup

        # if the concurrency is larger than the total credits, it does not matter
        # as it is simply an upper bound that will never be reached
        self._concurrency = config.concurrency
        self._semaphore = asyncio.Semaphore(value=self._concurrency)

        self.logger.info(
            "TM: Concurrency Strategy initialized with total_credits=%s, concurrency=%s, warmup=%s",
            self.active_phase.total_credits,
            self._concurrency,
            config.warmup_request_count,
        )

    async def start(self) -> None:
        """Start the credit issuing strategy. This will launch the progress reporting loop, the
        warmup phase (if applicable), and the profiling phase, all in the background."""

        if self.warmup:
            self.execute_async(self._execute_phase(self.warmup))
        self.execute_async(
            self._execute_phase(
                self.profiling, self.warmup.completed_event if self.warmup else None
            )
        )

    async def _execute_phase(
        self, phase: CreditPhase, wait_for_event: asyncio.Event | None = None
    ) -> None:
        """Execute a phase of credit issuing. If a wait_for_event is provided,
        it will wait for the event to be set before executing the phase."""

        if wait_for_event is not None:
            self.logger.info("TM: Waiting for warmup to complete")
            await wait_for_event.wait()
            self.logger.info("TM: Warmup completed")

        self.active_phase = phase
        phase.start_time_ns = time.time_ns()

        self.logger.info(
            "TM: Executing phase (total_credits=%s, concurrency=%s, phase_type=%s, start_time_ns=%s)",
            phase.total_credits,
            self._concurrency,
            phase.phase_type,
            phase.start_time_ns,
        )

        # Start the progress reporting loop in the background
        self.execute_async(self._progress_report_loop())

        while phase.sent_credits < phase.total_credits:
            await self._semaphore.acquire()
            self.execute_async(
                self.credit_manager.drop_credit(
                    credit_phase=phase.phase_type,
                    conversation_id=None,
                    credit_drop_ns=None,
                )
            )
            phase.sent_credits += 1

        self.logger.debug("TM: Sent all credits for phase %s", phase)

    async def on_credit_return(self, message: CreditReturnMessage) -> None:
        """Process a credit return message."""

        self._semaphore.release()
        self.active_phase.completed_credits += 1

        diff_ns, per_sec = 0, 0.0
        if self.logger.isEnabledFor(logging.DEBUG):
            # Only calculate if debug logging is enabled
            diff_ns = time.time_ns() - self.active_phase.start_time_ns
            per_sec = (
                self.active_phase.completed_credits / (diff_ns / NANOS_PER_SECOND)
                if diff_ns > 0
                else 0
            )
            self.logger.debug(
                "TM: Processing credit return: %s (completed credits: %s of %s) (%.2f requests/s)",
                message,
                self.active_phase.completed_credits,
                self.active_phase.total_credits,
                per_sec,
            )

        if self.active_phase.completed_credits >= self.active_phase.total_credits:
            self.active_phase.end_time_ns = time.time_ns()
            self.execute_async(
                self.credit_manager.publish_credits_complete(
                    self.active_phase.phase_type, False
                )
            )

            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(
                    "TM: All credits completed, stopping credit drop task after %.2f seconds (%.2f requests/s)",
                    diff_ns / NANOS_PER_SECOND,
                    per_sec,
                )
                self.active_phase.completed_event.set()

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
        self.logger.debug("TM: Starting progress reporting loop")
        while not self.active_phase.completed_event.is_set():
            try:
                await self._report_progress()
            except asyncio.CancelledError:
                self.logger.debug("TM: Progress reporting loop cancelled")
                return

            await asyncio.sleep(1)  # TODO: Make this configurable

        self.logger.debug(
            "TM: All credits completed for phase %s, stopping progress reporting loop",
            self.active_phase,
        )

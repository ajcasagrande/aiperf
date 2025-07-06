# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import time

from aiperf.common.exceptions import InvalidStateError
from aiperf.common.messages import CreditReturnMessage
from aiperf.services.timing_manager.config import TimingManagerConfig
from aiperf.services.timing_manager.credit_issuing_strategy import (
    CreditIssuingStrategy,
    CreditManagerProtocol,
)


class RateStrategy(CreditIssuingStrategy):
    """
    Class for rate credit issuing strategy.
    """

    def __init__(
        self, config: TimingManagerConfig, credit_manager: CreditManagerProtocol
    ):
        super().__init__(config=config, credit_manager=credit_manager)

        if config.request_rate is None:
            raise InvalidStateError("Request rate is not set")

        self._request_rate = config.request_rate
        self._total_credits = config.request_count
        self._warmup_request_count = config.warmup_request_count

        self._sent_credits = 0
        self._completed_credits = 0
        self.start_time_ns = 0

    async def start(self) -> None:
        self.start_time_ns = time.time_ns()
        self.execute_async(self._progress_report_loop())
        self.execute_async(self._credit_drop_loop())

    async def _credit_drop_loop(self) -> None:
        """Issue credit drops to workers."""

        await asyncio.sleep(1.5)  # TODO: HACK: Wait for the system to be ready

        self.logger.info(
            "TM: Issuing credit drops: %s total credits, %s request rate",
            self._total_credits,
            self._request_rate,
        )

        while self._sent_credits < self._total_credits:
            wait_duration_sec = 1.0 / self._request_rate

            if wait_duration_sec > 0:
                await asyncio.sleep(wait_duration_sec)

            self.execute_async(
                self.credit_manager.drop_credit(
                    conversation_id=None,
                    credit_drop_ns=None,
                )
            )

            self._sent_credits += 1

        self.logger.info("TM: All credits sent, stopping credit drop loop")

    async def _progress_report_loop(self) -> None:
        """Report progress."""

        while True:
            try:
                await self.credit_manager.publish_progress(
                    self.start_time_ns, self._total_credits, self._completed_credits
                )
            except asyncio.CancelledError:
                self.logger.debug("TM: Progress reporting loop cancelled")
                break

    async def on_credit_return(self, message: CreditReturnMessage) -> None:
        """Process a credit return message."""

        self._completed_credits += 1
        if self._completed_credits >= self._total_credits:
            self.logger.info("TM: All credits completed")
            self.execute_async(
                self.credit_manager.publish_credits_complete(cancelled=False)
            )

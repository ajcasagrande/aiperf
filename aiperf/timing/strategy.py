#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Protocol

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.config.timing_config import (
    TimingConfig,
    TimingManagerConfig,
    TimingMode,
)
from aiperf.common.hooks import on_configure, on_stop
from aiperf.common.messages import (
    CommandMessage,
    CreditDropMessage,
    CreditReturnMessage,
)
from aiperf.common.service.base_service import BaseService

TASK_CANCEL_TIMEOUT_SHORT = 1.0


class CreditManagerProtocol(Protocol):
    async def drop_credit(
        self,
        amount: int = 1,
        conversation_id: str | None = None,
        credit_drop_ns: int | None = None,
    ) -> None:
        pass


class CreditIssuingStrategy(ABC):
    """
    Base class for credit issuing strategies.
    """

    def __init__(self, config: TimingConfig, credit_manager: CreditManagerProtocol):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.credit_manager = credit_manager

    @abstractmethod
    async def initialize(self) -> None:
        pass

    @abstractmethod
    async def start(self) -> None:
        pass

    async def on_credit_return(self, message: CreditReturnMessage) -> None:
        """This is called by the credit manager when a credit is returned. It can be
        overridden in subclasses to handle the credit return."""
        return

    async def drop_credit(
        self,
        amount: int = 1,
        conversation_id: str | None = None,
        credit_drop_ns: int | None = None,
    ) -> None:
        """Request the credit manager to drop a credit."""
        asyncio.create_task(
            self.credit_manager.drop_credit(amount, conversation_id, credit_drop_ns)
        )


# ....


class FixedScheduleStrategy(CreditIssuingStrategy):
    async def run(self) -> None:
        # ...
        await self.drop_credit(
            amount=1,
            conversation_id="123",
            credit_drop_ns=None,
        )


class TimingManager(BaseService):
    def __init__(self, service_config: ServiceConfig, service_id: str | None = None):
        super().__init__(service_config=service_config, service_id=service_id)
        self.config = TimingManagerConfig()
        self._credit_issuing_strategy: CreditIssuingStrategy | None = None
        self.tasks: set[asyncio.Task] = set()

    @on_configure
    async def _configure(self, message: CommandMessage) -> None:
        """Configure the timing manager."""
        self.logger.debug("Configuring timing manager with message: %s", message)

        # config = TimingManagerConfig(message.data)
        config = TimingManagerConfig()
        assert isinstance(config, TimingManagerConfig)

        if config.timing_mode == TimingMode.FIXED_SCHEDULE:
            self._credit_issuing_strategy = FixedScheduleStrategy(config, self)

    async def _issue_credit_drops(self) -> None:
        """Issue credit drops according to the configured strategy."""
        if self._credit_issuing_strategy:
            task = asyncio.create_task(self._credit_issuing_strategy.start())
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)

            # wait until the credit issuing strategy is done
            await task

    async def _on_credit_return(self, message: CreditReturnMessage) -> None:
        """Handle a credit return message"""
        if self._credit_issuing_strategy:
            task = asyncio.create_task(
                self._credit_issuing_strategy.on_credit_return(message)
            )
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)

    async def drop_credit(
        self,
        amount: int = 1,
        conversation_id: str | None = None,
        credit_drop_ns: int | None = None,
    ) -> None:
        """Drop a credit. This will be called by the timing strategy."""
        task = asyncio.create_task(
            self.comms.push(
                CreditDropMessage(
                    service_id=self.service_id,
                    amount=amount,
                    conversation_id=conversation_id,
                    credit_drop_ns=credit_drop_ns,
                )
            )
        )
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    @on_stop
    async def _stop(self) -> None:
        """Stop the timing manager."""
        for task in list(self.tasks):
            task.cancel()

        await asyncio.wait_for(
            asyncio.gather(*self.tasks),
            timeout=TASK_CANCEL_TIMEOUT_SHORT,
        )
        self.tasks.clear()

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
from abc import ABC, abstractmethod
from typing import Protocol

from aiperf.common.messages import CreditReturnMessage


class CreditManagerProtocol(Protocol):
    """Protocol for a CreditManager. In most cases, this will be the TimingManager,
    and using this protocol allows the credit issuing strategy to be decoupled from the TimingManager.
    """

    async def drop_credit(
        self,
        amount: int = 1,
        conversation_id: str | None = None,
        credit_drop_ns: int | None = None,
    ) -> None: ...


class CreditIssuingStrategy(ABC):
    """
    Base class for credit issuing strategies.
    """

    def __init__(self, config, credit_manager: CreditManagerProtocol):
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
        """This is called by the credit manager when a credit is returned. By default
        it does nothing, however it can be overridden in subclasses to handle the credit return."""
        return

    async def drop_credit(
        self,
        amount: int = 1,
        conversation_id: str | None = None,
        credit_drop_ns: int | None = None,
    ) -> None:
        """Request the credit manager to drop a credit."""
        # NOTE: The timing manager will run this in a background task, so no need to wrap in asyncio.create_task
        await self.credit_manager.drop_credit(amount, conversation_id, credit_drop_ns)

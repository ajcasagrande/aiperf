#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import abc
from typing import Protocol

from aiperf.common.comms.base import PubClientProtocol as PubClientProtocol
from aiperf.common.enums import CreditPhase as CreditPhase
from aiperf.common.messages import (
    CreditPhaseCompleteMessage as CreditPhaseCompleteMessage,
)
from aiperf.common.messages import (
    CreditPhaseProgressMessage as CreditPhaseProgressMessage,
)
from aiperf.common.messages import (
    CreditPhaseSendingCompleteMessage as CreditPhaseSendingCompleteMessage,
)
from aiperf.common.messages import CreditPhaseStartMessage as CreditPhaseStartMessage
from aiperf.common.messages import CreditsCompleteMessage as CreditsCompleteMessage
from aiperf.common.mixins import AIPerfLoggerProtocol as AIPerfLoggerProtocol
from aiperf.common.mixins import AsyncTaskManagerMixin as AsyncTaskManagerMixin
from aiperf.common.mixins import AsyncTaskManagerProtocol as AsyncTaskManagerProtocol

class CreditManagerProtocol(Protocol):
    async def drop_credit(
        self,
        credit_phase: CreditPhase,
        conversation_id: str | None = None,
        credit_drop_ns: int | None = None,
    ) -> None: ...
    async def publish_progress(
        self, phase: CreditPhase, sent: int, completed: int
    ) -> None: ...
    async def publish_credits_complete(self) -> None: ...
    async def publish_phase_start(
        self,
        phase: CreditPhase,
        start_ns: int,
        total_expected_requests: int | None,
        expected_duration_sec: float | None,
    ) -> None: ...
    async def publish_phase_sending_complete(
        self, phase: CreditPhase, sent_end_ns: int
    ) -> None: ...
    async def publish_phase_complete(
        self, phase: CreditPhase, completed: int, end_ns: int
    ) -> None: ...

class CreditPhaseMessagesRequirements(
    AsyncTaskManagerProtocol, AIPerfLoggerProtocol, Protocol
):
    pub_client: PubClientProtocol
    service_id: str

class CreditPhaseMessagesMixin(
    AsyncTaskManagerMixin, CreditPhaseMessagesRequirements, metaclass=abc.ABCMeta
):
    def __init__(self, **kwargs) -> None: ...
    async def publish_phase_start(
        self,
        phase: CreditPhase,
        start_ns: int,
        total_expected_requests: int | None,
        expected_duration_sec: float | None,
    ) -> None: ...
    async def publish_phase_sending_complete(
        self, phase: CreditPhase, sent_end_ns: int
    ) -> None: ...
    async def publish_phase_complete(
        self, phase: CreditPhase, completed: int, end_ns: int
    ) -> None: ...
    async def publish_progress(
        self, phase: CreditPhase, sent: int, completed: int
    ) -> None: ...
    async def publish_credits_complete(self) -> None: ...

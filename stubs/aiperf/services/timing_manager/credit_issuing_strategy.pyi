#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import abc
from abc import ABC

from _typeshed import Incomplete

from aiperf.common.credit_models import CreditPhaseConfig as CreditPhaseConfig
from aiperf.common.credit_models import CreditPhaseStats as CreditPhaseStats
from aiperf.common.enums import CreditPhase as CreditPhase
from aiperf.common.enums._timing import TimingMode as TimingMode
from aiperf.common.exceptions import ConfigurationError as ConfigurationError
from aiperf.common.factories import FactoryMixin as FactoryMixin
from aiperf.common.messages import CreditReturnMessage as CreditReturnMessage
from aiperf.common.mixins import AIPerfLoggerMixin as AIPerfLoggerMixin
from aiperf.common.mixins import AsyncTaskManagerMixin as AsyncTaskManagerMixin
from aiperf.services.timing_manager.config import (
    TimingManagerConfig as TimingManagerConfig,
)
from aiperf.services.timing_manager.credit_manager import (
    CreditManagerProtocol as CreditManagerProtocol,
)

class CreditIssuingStrategy(
    AsyncTaskManagerMixin, AIPerfLoggerMixin, ABC, metaclass=abc.ABCMeta
):
    config: Incomplete
    credit_manager: Incomplete
    all_phases_complete_event: Incomplete
    phase_stats: dict[CreditPhase, CreditPhaseStats]
    ordered_phase_configs: list[CreditPhaseConfig]
    def __init__(
        self, config: TimingManagerConfig, credit_manager: CreditManagerProtocol
    ) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...

class CreditIssuingStrategyFactory(FactoryMixin[TimingMode, CreditIssuingStrategy]): ...

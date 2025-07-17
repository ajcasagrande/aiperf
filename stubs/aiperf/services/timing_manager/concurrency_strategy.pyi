#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.constants import NANOS_PER_SECOND as NANOS_PER_SECOND
from aiperf.common.credit_models import CreditPhaseStats as CreditPhaseStats
from aiperf.common.enums import TimingMode as TimingMode
from aiperf.common.exceptions import InvalidStateError as InvalidStateError
from aiperf.common.messages import CreditReturnMessage as CreditReturnMessage
from aiperf.common.mixins import AIPerfLoggerMixin as AIPerfLoggerMixin
from aiperf.common.mixins import AsyncTaskManagerMixin as AsyncTaskManagerMixin
from aiperf.services.timing_manager.config import (
    TimingManagerConfig as TimingManagerConfig,
)
from aiperf.services.timing_manager.credit_issuing_strategy import (
    CreditIssuingStrategy as CreditIssuingStrategy,
)
from aiperf.services.timing_manager.credit_issuing_strategy import (
    CreditIssuingStrategyFactory as CreditIssuingStrategyFactory,
)
from aiperf.services.timing_manager.credit_issuing_strategy import (
    CreditManagerProtocol as CreditManagerProtocol,
)

class ConcurrencyStrategy(
    CreditIssuingStrategy, AsyncTaskManagerMixin, AIPerfLoggerMixin
):
    def __init__(
        self, config: TimingManagerConfig, credit_manager: CreditManagerProtocol
    ) -> None: ...

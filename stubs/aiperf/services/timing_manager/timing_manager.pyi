#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete

from aiperf.common.comms.base import (
    CommunicationClientAddressType as CommunicationClientAddressType,
)
from aiperf.common.comms.base import PullClientProtocol as PullClientProtocol
from aiperf.common.comms.base import PushClientProtocol as PushClientProtocol
from aiperf.common.comms.base import RequestClientProtocol as RequestClientProtocol
from aiperf.common.config import ServiceConfig as ServiceConfig
from aiperf.common.config.user_config import UserConfig as UserConfig
from aiperf.common.enums import CreditPhase as CreditPhase
from aiperf.common.enums import MessageType as MessageType
from aiperf.common.enums import ServiceType as ServiceType
from aiperf.common.exceptions import InvalidStateError as InvalidStateError
from aiperf.common.factories import ServiceFactory as ServiceFactory
from aiperf.common.hooks import on_configure as on_configure
from aiperf.common.hooks import on_init as on_init
from aiperf.common.hooks import on_start as on_start
from aiperf.common.hooks import on_stop as on_stop
from aiperf.common.messages import CommandMessage as CommandMessage
from aiperf.common.messages import CreditDropMessage as CreditDropMessage
from aiperf.common.messages import CreditReturnMessage as CreditReturnMessage
from aiperf.common.messages import DatasetTimingRequest as DatasetTimingRequest
from aiperf.common.messages import DatasetTimingResponse as DatasetTimingResponse
from aiperf.common.service.base_component_service import (
    BaseComponentService as BaseComponentService,
)
from aiperf.services.timing_manager.config import (
    TimingManagerConfig as TimingManagerConfig,
)
from aiperf.services.timing_manager.config import TimingMode as TimingMode
from aiperf.services.timing_manager.credit_issuing_strategy import (
    CreditIssuingStrategy as CreditIssuingStrategy,
)
from aiperf.services.timing_manager.credit_issuing_strategy import (
    CreditIssuingStrategyFactory as CreditIssuingStrategyFactory,
)
from aiperf.services.timing_manager.credit_manager import (
    CreditPhaseMessagesMixin as CreditPhaseMessagesMixin,
)

class TimingManager(BaseComponentService, CreditPhaseMessagesMixin):
    dataset_request_client: RequestClientProtocol
    credit_drop_push_client: PushClientProtocol
    credit_return_pull_client: PullClientProtocol
    user_config: Incomplete
    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig | None,
        service_id: str | None = None,
    ) -> None: ...
    @property
    def service_type(self) -> ServiceType: ...
    async def drop_credit(
        self,
        credit_phase: CreditPhase,
        conversation_id: str | None = None,
        credit_drop_ns: int | None = None,
    ) -> None: ...

def main() -> None: ...

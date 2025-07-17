#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete

from aiperf.clients import InferenceClientFactory as InferenceClientFactory
from aiperf.clients.client_interfaces import (
    RequestConverterFactory as RequestConverterFactory,
)
from aiperf.clients.model_endpoint_info import ModelEndpointInfo as ModelEndpointInfo
from aiperf.common.comms.base import PullClientProtocol as PullClientProtocol
from aiperf.common.comms.base import PushClientProtocol as PushClientProtocol
from aiperf.common.comms.base import RequestClientProtocol as RequestClientProtocol
from aiperf.common.config import ServiceConfig as ServiceConfig
from aiperf.common.config import UserConfig as UserConfig
from aiperf.common.constants import NANOS_PER_SECOND as NANOS_PER_SECOND
from aiperf.common.enums import (
    CommunicationClientAddressType as CommunicationClientAddressType,
)
from aiperf.common.enums import CreditPhase as CreditPhase
from aiperf.common.enums import MessageType as MessageType
from aiperf.common.enums import ServiceType as ServiceType
from aiperf.common.exceptions import NotInitializedError as NotInitializedError
from aiperf.common.factories import ServiceFactory as ServiceFactory
from aiperf.common.hooks import aiperf_task as aiperf_task
from aiperf.common.hooks import on_configure as on_configure
from aiperf.common.hooks import on_init as on_init
from aiperf.common.hooks import on_stop as on_stop
from aiperf.common.messages import CommandMessage as CommandMessage
from aiperf.common.messages import (
    ConversationRequestMessage as ConversationRequestMessage,
)
from aiperf.common.messages import (
    ConversationResponseMessage as ConversationResponseMessage,
)
from aiperf.common.messages import CreditDropMessage as CreditDropMessage
from aiperf.common.messages import CreditReturnMessage as CreditReturnMessage
from aiperf.common.messages import ErrorMessage as ErrorMessage
from aiperf.common.messages import InferenceResultsMessage as InferenceResultsMessage
from aiperf.common.messages import WorkerHealthMessage as WorkerHealthMessage
from aiperf.common.mixins import ProcessHealthMixin as ProcessHealthMixin
from aiperf.common.models import ErrorDetails as ErrorDetails
from aiperf.common.models import RequestRecord as RequestRecord
from aiperf.common.models import Turn as Turn
from aiperf.common.models import WorkerPhaseTaskStats as WorkerPhaseTaskStats
from aiperf.common.service.base_component_service import (
    BaseComponentService as BaseComponentService,
)

class Worker(BaseComponentService, ProcessHealthMixin):
    health_check_interval: Incomplete
    task_stats: dict[CreditPhase, WorkerPhaseTaskStats]
    credit_drop_pull_client: PullClientProtocol
    credit_return_push_client: PushClientProtocol
    inference_results_push_client: PushClientProtocol
    conversation_request_client: RequestClientProtocol
    model_endpoint: Incomplete
    request_converter: Incomplete
    inference_client: Incomplete
    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig | None = None,
        service_id: str | None = None,
        **kwargs,
    ) -> None: ...
    @property
    def service_type(self) -> ServiceType: ...
    def create_health_message(self) -> WorkerHealthMessage: ...

def main() -> None: ...

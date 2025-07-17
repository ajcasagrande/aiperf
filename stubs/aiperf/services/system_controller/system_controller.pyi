#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.config import ServiceConfig as ServiceConfig
from aiperf.common.config._user import UserConfig as UserConfig
from aiperf.common.enums import BenchmarkSuiteType as BenchmarkSuiteType
from aiperf.common.enums import CommandResponseStatus as CommandResponseStatus
from aiperf.common.enums import CommandType as CommandType
from aiperf.common.enums import MessageType as MessageType
from aiperf.common.enums import ServiceState as ServiceState
from aiperf.common.enums import ServiceType as ServiceType
from aiperf.common.enums import SystemState as SystemState
from aiperf.common.exceptions import CommunicationError as CommunicationError
from aiperf.common.exceptions import NotInitializedError as NotInitializedError
from aiperf.common.factories import ServiceFactory as ServiceFactory
from aiperf.common.hooks import on_cleanup as on_cleanup
from aiperf.common.hooks import on_message as on_message
from aiperf.common.hooks import on_start as on_start
from aiperf.common.hooks import on_stop as on_stop
from aiperf.common.messages import CommandResponseMessage as CommandResponseMessage
from aiperf.common.messages import HeartbeatMessage as HeartbeatMessage
from aiperf.common.messages import Message as Message
from aiperf.common.messages import (
    ProcessRecordsCommandData as ProcessRecordsCommandData,
)
from aiperf.common.messages import (
    RecordsProcessingStatsMessage as RecordsProcessingStatsMessage,
)
from aiperf.common.messages import RegistrationMessage as RegistrationMessage
from aiperf.common.messages import StatusMessage as StatusMessage
from aiperf.common.messages._progress import (
    ProfileResultsMessage as ProfileResultsMessage,
)
from aiperf.common.mixins import AIPerfMessageHandlerMixin as AIPerfMessageHandlerMixin
from aiperf.common.models import AIPerfBaseModel as AIPerfBaseModel
from aiperf.common.models import ServiceRegistrationInfo as ServiceRegistrationInfo
from aiperf.common.service.base_controller_service import (
    BaseControllerService as BaseControllerService,
)
from aiperf.data_exporter.exporter_manager import ExporterManager as ExporterManager
from aiperf.progress.progress_tracker import (
    BenchmarkSuiteProgress as BenchmarkSuiteProgress,
)
from aiperf.progress.progress_tracker import ProfileRunProgress as ProfileRunProgress
from aiperf.progress.progress_tracker import ProgressTracker as ProgressTracker
from aiperf.services.system_controller.profile_runner import (
    ProfileRunner as ProfileRunner,
)
from aiperf.services.system_controller.proxy_mixins import ProxyMixin as ProxyMixin
from aiperf.services.system_controller.service_manager_mixin import (
    ServiceManagerMixin as ServiceManagerMixin,
)
from aiperf.services.system_controller.system_mixins import (
    SignalHandlerMixin as SignalHandlerMixin,
)
from aiperf.ui import AIPerfUIProtocol as AIPerfUIProtocol
from aiperf.ui.ui_protocol import AIPerfUIFactory as AIPerfUIFactory

class SystemController(
    BaseControllerService,
    SignalHandlerMixin,
    ProxyMixin,
    ServiceManagerMixin,
    AIPerfMessageHandlerMixin,
):
    service_config: ServiceConfig
    user_config: UserConfig
    progress_tracker: ProgressTracker
    ui: AIPerfUIProtocol
    profile_runner: ProfileRunner | None
    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig | None = None,
        service_id: str | None = None,
        **kwargs,
    ) -> None: ...
    @property
    def service_type(self) -> ServiceType: ...
    async def initialize(self) -> None: ...
    async def start_profiling_all_services(self) -> None: ...
    async def send_command_to_service(
        self,
        target_service_id: str | None,
        command: CommandType,
        data: AIPerfBaseModel | None = None,
        target_service_type: ServiceType | None = None,
    ) -> None: ...
    async def kill(self) -> None: ...

def main() -> int: ...

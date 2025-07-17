#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import asyncio
from collections import deque

from _typeshed import Incomplete

from aiperf.common.comms.base import (
    CommunicationClientAddressType as CommunicationClientAddressType,
)
from aiperf.common.comms.base import PullClientProtocol as PullClientProtocol
from aiperf.common.config import ServiceConfig as ServiceConfig
from aiperf.common.config import ServiceDefaults as ServiceDefaults
from aiperf.common.config import UserConfig as UserConfig
from aiperf.common.credit_models import PhaseProcessingStats as PhaseProcessingStats
from aiperf.common.enums import CommandType as CommandType
from aiperf.common.enums import CreditPhase as CreditPhase
from aiperf.common.enums import MessageType as MessageType
from aiperf.common.enums import ServiceType as ServiceType
from aiperf.common.factories import ServiceFactory as ServiceFactory
from aiperf.common.hooks import aiperf_task as aiperf_task
from aiperf.common.hooks import on_cleanup as on_cleanup
from aiperf.common.hooks import on_configure as on_configure
from aiperf.common.hooks import on_init as on_init
from aiperf.common.hooks import on_start as on_start
from aiperf.common.hooks import on_stop as on_stop
from aiperf.common.messages import CommandMessage as CommandMessage
from aiperf.common.messages import InferenceResultsMessage as InferenceResultsMessage
from aiperf.common.messages import (
    ParsedInferenceResultsMessage as ParsedInferenceResultsMessage,
)
from aiperf.common.messages import (
    ProcessRecordsCommandData as ProcessRecordsCommandData,
)
from aiperf.common.messages import ProfileResultsMessage as ProfileResultsMessage
from aiperf.common.messages import (
    RecordsProcessingStatsMessage as RecordsProcessingStatsMessage,
)
from aiperf.common.messages._credit import (
    CreditPhaseCompleteMessage as CreditPhaseCompleteMessage,
)
from aiperf.common.messages._credit import (
    CreditPhaseStartMessage as CreditPhaseStartMessage,
)
from aiperf.common.record_models import ErrorDetails as ErrorDetails
from aiperf.common.record_models import ErrorDetailsCount as ErrorDetailsCount
from aiperf.common.record_models import ParsedResponseRecord as ParsedResponseRecord
from aiperf.common.service import BaseComponentService as BaseComponentService
from aiperf.data_exporter.exporter_manager import ExporterManager as ExporterManager
from aiperf.services.records_manager.post_processors.metric_summary import (
    MetricSummary as MetricSummary,
)

class RecordsManager(BaseComponentService):
    user_config: UserConfig | None
    configured_event: Incomplete
    records: deque[ParsedResponseRecord]
    error_records: deque[ParsedResponseRecord]
    total_expected_requests: int | None
    error_records_count: int
    records_count: int
    final_request_count: int | None
    worker_success_counts: dict[str, int]
    worker_error_counts: dict[str, int]
    start_time_ns: int
    end_time_ns: int | None
    incoming_records: asyncio.Queue[InferenceResultsMessage]
    response_results_client: PullClientProtocol
    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str | None = None,
    ) -> None: ...
    @property
    def service_type(self) -> ServiceType: ...
    async def publish_processing_stats(self) -> None: ...
    async def get_error_summary(self) -> list[ErrorDetailsCount]: ...
    was_cancelled: Incomplete
    async def process_records(self, message: CommandMessage) -> None: ...
    async def post_process_records(self) -> ProfileResultsMessage | None: ...

def main() -> None: ...

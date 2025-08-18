# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.base_component_service import BaseComponentService
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.constants import DEFAULT_PULL_CLIENT_MAX_CONCURRENCY
from aiperf.common.enums import CommAddress, CommandType, MessageType, ServiceType
from aiperf.common.factories import (
    ServiceFactory,
)
from aiperf.common.hooks import (
    on_command,
    on_pull_message,
)
from aiperf.common.messages import (
    InferenceResultsMessage,
    ProfileConfigureCommand,
)
from aiperf.common.mixins import PullClientMixin
from aiperf.records.record_processor_mixin import RecordProcessorMixin


@ServiceFactory.register(ServiceType.RECORD_PROCESSOR)
class RecordProcessor(PullClientMixin, RecordProcessorMixin, BaseComponentService):
    """RecordProcessor is responsible for processing the records and pushing them to the RecordsManager.
    This service is meant to be run in a distributed fashion, where the amount of record processors can be scaled
    based on the load of the system.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
            pull_client_address=CommAddress.RAW_INFERENCE_PROXY_BACKEND,
            pull_client_bind=False,
            pull_client_max_concurrency=DEFAULT_PULL_CLIENT_MAX_CONCURRENCY,
            **kwargs,
        )

    @on_command(CommandType.PROFILE_CONFIGURE)
    async def _profile_configure_command(
        self, message: ProfileConfigureCommand
    ) -> None:
        """Configure the record processor."""
        await self.configure()

    @on_pull_message(MessageType.INFERENCE_RESULTS)
    async def _on_inference_results(self, message: InferenceResultsMessage) -> None:
        """Handle an inference results message."""
        await self.process_request_record(message.service_id, message.record)


def main() -> None:
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(RecordProcessor)


if __name__ == "__main__":
    main()

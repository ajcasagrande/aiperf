# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import time

from aiperf.common.comms.base_comms import (
    CommunicationClientAddressType,
    PullClientProtocol,
)
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import (
    CreditPhase,
    MessageType,
    ServiceType,
)
from aiperf.common.factories import ServiceFactory, StreamingPostProcessorFactory
from aiperf.common.hooks import on_init
from aiperf.common.messages import (
    ParsedInferenceResultsMessage,
)
from aiperf.common.service import BaseComponentService
from aiperf.services.records_manager.streaming_post_processor import (
    StreamingPostProcessor,
)


@ServiceFactory.register(ServiceType.RECORDS_MANAGER)
class RecordsManager(BaseComponentService):
    """
    The RecordsManager service is primarily responsible for holding the
    results returned from the workers.
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
            **kwargs,
        )

        self.start_time_ns: int = time.time_ns()
        self.end_time_ns: int | None = None

        self.response_results_client: PullClientProtocol = (
            self.comms.create_pull_client(
                CommunicationClientAddressType.RECORDS,
                bind=True,
            )
        )
        self.response_streamers: list[StreamingPostProcessor] = []

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.RECORDS_MANAGER

    @on_init
    async def _initialize(self) -> None:
        """Initialize records manager-specific components."""
        self.debug("Initializing records manager")

        await self.response_results_client.register_pull_callback(
            message_type=MessageType.PARSED_INFERENCE_RESULTS,
            callback=self._on_parsed_inference_results,
            max_concurrency=100_000,
        )

        # Initialize the all of the response streamers
        self.response_streamers: list[StreamingPostProcessor] = [
            StreamingPostProcessorFactory.create_instance(
                class_type=streamer_type,
                pub_client=self.pub_client,
                sub_client=self.sub_client,
                service_id=self.service_id,
                service_config=self.service_config,
                user_config=self.user_config,
            )
            for streamer_type in StreamingPostProcessorFactory.get_all_class_types()
        ]
        self.info(
            lambda: f"Initialized {len(self.response_streamers)} response streamers"
        )
        # Start the lifecycle for all response streamers
        for streamer in self.response_streamers:
            self.debug(
                lambda streamer=streamer: f"Starting lifecycle for {streamer.__class__.__name__}"
            )
            await streamer.run_async()

    async def _on_parsed_inference_results(
        self, message: ParsedInferenceResultsMessage
    ) -> None:
        """Handle a parsed inference results message."""
        if message.record.request.credit_phase != CreditPhase.PROFILING:
            self.debug(
                lambda: f"Skipping non-profiling record: {message.record.request.credit_phase}"
            )
            return

        for streamer in self.response_streamers:
            self.execute_async(streamer.stream_record(message.record))


def main() -> None:
    """Main entry point for the records manager."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(RecordsManager)


if __name__ == "__main__":
    main()

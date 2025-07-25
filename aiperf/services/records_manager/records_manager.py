# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import sys
from typing import Any

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import (
    CommAddress,
    CommandType,
    CreditPhase,
    MessageType,
    ServiceType,
)
from aiperf.common.factories import ServiceFactory, StreamingPostProcessorFactory
from aiperf.common.hooks import (
    command_handler,
    implements_protocol,
    on_init,
    on_pull_message,
    on_start,
    on_stop,
)
from aiperf.common.messages import (
    CommandMessage,
    ParsedInferenceResultsMessage,
)
from aiperf.common.mixins import PullClientMixin
from aiperf.common.protocols import ServiceProtocol
from aiperf.services.base_component_service import BaseComponentService
from aiperf.services.records_manager.post_processors import BaseStreamingPostProcessor

DEFAULT_MAX_RECORDS_CONCURRENCY = 100_000
"""The default maximum concurrency for the records manager pull client."""


@implements_protocol(ServiceProtocol)
@ServiceFactory.register(ServiceType.RECORDS_MANAGER)
class RecordsManager(PullClientMixin, BaseComponentService):
    """
    The RecordsManager service is primarily responsible for holding the
    results returned from the workers.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str | None = None,
    ) -> None:
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
            pull_client_address=CommAddress.RECORDS,
            pull_client_bind=True,
        )
        self.streaming_post_processors: list[BaseStreamingPostProcessor] = []

    @on_init
    async def _initialize_streaming_post_processors(self) -> None:
        """Initialize the streaming post processors and start their lifecycle."""
        self.debug("Initializing streaming post processors")
        for streamer_type in StreamingPostProcessorFactory.get_all_class_types():
            streamer = StreamingPostProcessorFactory.create_instance(
                class_type=streamer_type,
                service_id=self.service_id,
                service_config=self.service_config,
                user_config=self.user_config,
            )
            self.debug(
                f"Initializing streaming post processor: {streamer_type}: {streamer.__class__.__name__}"
            )
            self.streaming_post_processors.append(streamer)
            self.debug(
                lambda streamer=streamer: f"Starting lifecycle for {streamer.__class__.__name__}"
            )
            await streamer.initialize()

    @on_start
    async def _start_streaming_post_processors(self) -> None:
        """Start the streaming post processors."""
        for streamer in self.streaming_post_processors:
            self.debug(
                lambda streamer=streamer: f"Starting {streamer.__class__.__name__}"
            )
            await streamer.start()

    @on_stop
    async def _stop_streaming_post_processors(self) -> None:
        """Stop the streaming post processors."""
        await asyncio.gather(
            *[streamer.stop() for streamer in self.streaming_post_processors],
            return_exceptions=True,
        )

    @on_pull_message(
        MessageType.PARSED_INFERENCE_RESULTS,
        max_concurrency=DEFAULT_MAX_RECORDS_CONCURRENCY,
    )
    async def _on_parsed_inference_results(
        self, message: ParsedInferenceResultsMessage
    ) -> None:
        """Handle a parsed inference results message."""
        self.trace(lambda: f"Received parsed inference results: {message}")

        if message.record.request.credit_phase != CreditPhase.PROFILING:
            self.debug(
                lambda: f"Skipping non-profiling record: {message.record.request.credit_phase}"
            )
            return

        # Stream the record to all of the streaming post processors
        for streamer in self.streaming_post_processors:
            try:
                self.debug(
                    lambda name=streamer.__class__.__name__: f"Putting record into queue for streamer {name}"
                )
                streamer.records_queue.put_nowait(message.record)
            except asyncio.QueueFull:
                self.error(
                    f"Streaming post processor {streamer.__class__.__name__} is unable to keep up with the rate of incoming records."
                )
                self.warning(
                    f"Waiting for queue to be available for streamer {streamer.__class__.__name__}. This will cause back pressure on the records manager."
                )
                await streamer.records_queue.put(message.record)

    @command_handler(CommandType.PROCESS_RECORDS)
    async def _on_process_records_command(self, message: CommandMessage) -> list[Any]:
        """Handle the process records command by forwarding it to all of the streaming post processors, and returning the results."""
        self.debug(lambda: f"Received process records command: {message}")
        # TODO: Do we need to handle errors from the streaming post processors?
        results = await asyncio.gather(
            *[
                streamer.on_process_records_command(message)
                for streamer in self.streaming_post_processors
            ],
            return_exceptions=True,
        )
        return results


def main() -> None:
    """Main entry point for the records manager."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(RecordsManager)


if __name__ == "__main__":
    sys.exit(main())

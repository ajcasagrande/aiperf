# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio

from aiperf.common.base_component_service import BaseComponentService
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.constants import DEFAULT_PULL_CLIENT_MAX_CONCURRENCY
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import (
    CommAddress,
    CommandType,
    MessageType,
    ServiceType,
)
from aiperf.common.factories import (
    ResultsProcessorFactory,
    ServiceFactory,
)
from aiperf.common.hooks import on_command, on_message, on_pull_message
from aiperf.common.messages import (
    ProcessRecordsCommand,
)
from aiperf.common.messages.command_messages import ProfileCancelCommand
from aiperf.common.messages.inference_messages import MetricRecordsMessage
from aiperf.common.messages.progress_messages import (
    AllRecordsReceivedMessage,
    ProcessRecordsResultMessage,
)
from aiperf.common.mixins import PullClientMixin
from aiperf.common.models.error_models import ErrorDetails
from aiperf.common.models.record_models import ProcessRecordsResult, ProfileResults
from aiperf.common.protocols import ResultsProcessorProtocol, ServiceProtocol


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
            pull_client_max_concurrency=DEFAULT_PULL_CLIENT_MAX_CONCURRENCY,
        )
        self._profile_cancelled = False

        self._results_processors: list[ResultsProcessorProtocol] = []
        for results_processor_type in ResultsProcessorFactory.get_all_class_types():
            results_processor = ResultsProcessorFactory.create_instance(
                class_type=results_processor_type,
                service_id=self.service_id,
                service_config=self.service_config,
                user_config=self.user_config,
            )
            self.debug(
                f"Created results processor: {results_processor_type}: {results_processor.__class__.__name__}"
            )
            self._results_processors.append(results_processor)
            self.attach_child_lifecycle(results_processor)

    @on_pull_message(MessageType.METRIC_RECORDS)
    async def _on_metric_records(self, message: MetricRecordsMessage) -> None:
        """Handle a metric records message."""
        self.trace(lambda: f"Received metric records: {message}")
        await asyncio.gather(
            *[
                results_processor.process_result(result)
                for results_processor in self._results_processors
                for result in message.results
            ]
        )

    # @on_pull_message(MessageType.PARSED_INFERENCE_RESULTS)
    # async def _on_parsed_inference_results(
    #     self, message: ParsedInferenceResultsMessage
    # ) -> None:
    #     """Handle a parsed inference results message."""
    #     self.trace(lambda: f"Received parsed inference results: {message}")

    #     if self._profile_cancelled:
    #         self.debug("Skipping record because profiling is cancelled")
    #         return

    #     if message.record.request.credit_phase != CreditPhase.PROFILING:
    #         self.debug(
    #             lambda: f"Skipping non-profiling record: {message.record.request.credit_phase}"
    #         )
    #         return

    #     # Stream the record to all of the streaming post processors
    #     for streamer in self.streaming_post_processors:
    #         try:
    #             self.debug(
    #                 lambda name=streamer.__class__.__name__: f"Putting record into queue for streamer {name}"
    #             )
    #             streamer.records_queue.put_nowait(message.record)
    #         except asyncio.QueueFull:
    #             self.error(
    #                 f"Streaming post processor {streamer.__class__.__name__} is unable to keep up with the rate of incoming records."
    #             )
    #             self.warning(
    #                 f"Waiting for queue to be available for streamer {streamer.__class__.__name__}. This will cause back pressure on the records manager."
    #             )
    #             await streamer.records_queue.put(message.record)

    @on_command(CommandType.PROCESS_RECORDS)
    async def _on_process_records_command(
        self, message: ProcessRecordsCommand
    ) -> ProcessRecordsResult:
        """Handle the process records command by forwarding it to all of the streaming post processors, and returning the results."""
        self.debug(lambda: f"Received process records command: {message}")
        return await self._process_records(cancelled=message.cancelled)

    @on_command(CommandType.PROFILE_CANCEL)
    async def _on_profile_cancel_command(
        self, message: ProfileCancelCommand
    ) -> ProcessRecordsResult:
        """Handle the profile cancel command by cancelling the streaming post processors."""
        self.debug(lambda: f"Received profile cancel command: {message}")
        self._profile_cancelled = True
        # for results_processor in self._results_processors:
        #     results_processor.stop_requested = True
        return await self._process_records(cancelled=True)

    @on_message(MessageType.ALL_RECORDS_RECEIVED)
    async def _on_all_records_received(
        self, message: AllRecordsReceivedMessage
    ) -> None:
        """Handle a all records received message."""
        self.debug(lambda: f"Received all records: {message}, processing now...")
        await self._process_records(cancelled=self._profile_cancelled)

    async def _process_records(self, cancelled: bool) -> ProcessRecordsResult:
        """Process the records."""
        self.debug(lambda: f"Processing records (cancelled: {cancelled})")

        # Process the records through the results processors
        results = await asyncio.gather(
            *[
                results_processor.summarize()
                for results_processor in self._results_processors
            ],
            return_exceptions=True,
        )
        self.info(lambda: f"Processed records results: {results}")

        records_results = [
            result for result in results if isinstance(result, ProfileResults)
        ]
        error_results = [
            result for result in results if isinstance(result, ErrorDetails)
        ]

        result = ProcessRecordsResult(records=records_results, errors=error_results)
        self.debug(lambda: f"Processed records result: {result}")
        await self.publish(
            ProcessRecordsResultMessage(
                service_id=self.service_id,
                process_records_result=result,
            )
        )
        return result


def main() -> None:
    """Main entry point for the records manager."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(RecordsManager)


if __name__ == "__main__":
    main()

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import sys

import pandas as pd

from aiperf.common.comms.client_enums import ClientType, PullClientType
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.constants import NANOS_PER_MILLIS
from aiperf.common.data_exporter.record import Record
from aiperf.common.enums import MessageType, ServiceType, Topic
from aiperf.common.factories import ServiceFactory
from aiperf.common.hooks import (
    on_cleanup,
    on_configure,
    on_init,
    on_start,
    on_stop,
)
from aiperf.common.messages import (
    InferenceResultsMessage,
    Message,
    ProfileResultsMessage,
)
from aiperf.common.record_models import RequestErrorRecord, RequestRecord
from aiperf.common.service.base_component_service import BaseComponentService


@ServiceFactory.register(ServiceType.RECORDS_MANAGER)
class RecordsManager(BaseComponentService):
    """
    The RecordsManager service is primarily responsible for holding the
    results returned from the workers.
    """

    def __init__(
        self, service_config: ServiceConfig, service_id: str | None = None
    ) -> None:
        super().__init__(service_config=service_config, service_id=service_id)
        self.logger.debug("Initializing records manager")

        self.records: list[RequestRecord] = []
        self.error_records: list[RequestErrorRecord] = []

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.RECORDS_MANAGER

    @property
    def required_clients(self) -> list[ClientType]:
        """The required clients."""
        return [
            *(super().required_clients or []),
            PullClientType.INFERENCE_RESULTS,
        ]

    @on_init
    async def _initialize(self) -> None:
        """Initialize records manager-specific components."""
        self.logger.debug("Initializing records manager")
        # TODO: Implement records manager initialization

    @on_start
    async def _start(self) -> None:
        """Start the records manager."""
        self.logger.debug("Starting records manager")
        # TODO: Implement records manager start
        self.logger.debug("Pulling inference results")
        await self.comms.register_pull_callback(
            message_type=MessageType.INFERENCE_RESULTS,
            callback=self._on_inference_results,
        )

    @on_stop
    async def _stop(self) -> None:
        """Stop the records manager."""
        self.logger.debug("Stopping records manager")
        # TODO: Implement records manager stop
        await self.process_records()

    @on_cleanup
    async def _cleanup(self) -> None:
        """Clean up records manager-specific components."""
        self.logger.debug("Cleaning up records manager")
        # TODO: Implement records manager cleanup

    @on_configure
    async def _configure(self, message: Message) -> None:
        """Configure the records manager."""
        self.logger.debug(f"Configuring records manager with message: {message}")
        # TODO: Implement records manager configuration

    async def _on_inference_results(self, message: InferenceResultsMessage) -> None:
        """Handle a inference results message."""
        record = message.record

        if isinstance(record, RequestErrorRecord):
            self.logger.error(f"Received inference results error: {record.error}")
            self.error_records.append(record)
        elif isinstance(record, RequestRecord):
            self.logger.debug(
                f"Received inference results: {record.time_to_first_response_ns / NANOS_PER_MILLIS} milliseconds. {record.time_to_last_response_ns / NANOS_PER_MILLIS} milliseconds."
            )
            self.records.append(record)
        else:
            self.logger.error(f"Unknown inference results type: {type(record)}")

    async def process_records(self) -> None:
        """Process the records."""
        self.logger.debug("Processing records")
        # TODO: Implement records processing
        self.logger.debug(f"Processed {len(self.records)} successful records")
        self.logger.debug(f"Processed {len(self.error_records)} error records")

        profile_results = await self.post_process_records()
        if profile_results:
            await self.comms.publish(
                topic=Topic.PROFILE_RESULTS,
                message=profile_results,
            )

    async def post_process_records(self) -> ProfileResultsMessage | None:
        """Post process the records."""
        self.logger.debug("Post processing records")

        if not self.records:
            self.logger.warning("No successful records to process")
            return None

        # Extract time to first response values
        time_to_first_response_values = [
            record.time_to_first_response_ns for record in self.records
        ]
        time_to_last_response_values = [
            record.time_to_last_response_ns for record in self.records
        ]
        inter_token_latency_values = [
            record.inter_token_latency_ns for record in self.records
        ]

        # Create single DataFrame with all metrics
        metrics_df = pd.DataFrame(
            {
                "ttft_ns": time_to_first_response_values,
                "ttlt_ns": time_to_last_response_values,
                "itl_ns": inter_token_latency_values,
            }
        )

        # Create Record objects (converting from ns to ms)
        ttft_record = Record(
            name="Time to First Token",
            unit="ms",
            avg=metrics_df["ttft_ns"].mean() / NANOS_PER_MILLIS,
            min=metrics_df["ttft_ns"].min() / NANOS_PER_MILLIS,
            max=metrics_df["ttft_ns"].max() / NANOS_PER_MILLIS,
            p1=metrics_df["ttft_ns"].quantile(0.01) / NANOS_PER_MILLIS,
            p5=metrics_df["ttft_ns"].quantile(0.05) / NANOS_PER_MILLIS,
            p25=metrics_df["ttft_ns"].quantile(0.25) / NANOS_PER_MILLIS,
            p50=metrics_df["ttft_ns"].quantile(0.50) / NANOS_PER_MILLIS,
            p75=metrics_df["ttft_ns"].quantile(0.75) / NANOS_PER_MILLIS,
            p90=metrics_df["ttft_ns"].quantile(0.90) / NANOS_PER_MILLIS,
            p95=metrics_df["ttft_ns"].quantile(0.95) / NANOS_PER_MILLIS,
            p99=metrics_df["ttft_ns"].quantile(0.99) / NANOS_PER_MILLIS,
            std=metrics_df["ttft_ns"].std() / NANOS_PER_MILLIS,
            streaming_only=True,
        )

        ttlt_record = Record(
            name="Time to Last Token",
            unit="ms",
            avg=metrics_df["ttlt_ns"].mean() / NANOS_PER_MILLIS,
            min=metrics_df["ttlt_ns"].min() / NANOS_PER_MILLIS,
            max=metrics_df["ttlt_ns"].max() / NANOS_PER_MILLIS,
            p1=metrics_df["ttlt_ns"].quantile(0.01) / NANOS_PER_MILLIS,
            p5=metrics_df["ttlt_ns"].quantile(0.05) / NANOS_PER_MILLIS,
            p25=metrics_df["ttlt_ns"].quantile(0.25) / NANOS_PER_MILLIS,
            p50=metrics_df["ttlt_ns"].quantile(0.50) / NANOS_PER_MILLIS,
            p75=metrics_df["ttlt_ns"].quantile(0.75) / NANOS_PER_MILLIS,
            p90=metrics_df["ttlt_ns"].quantile(0.90) / NANOS_PER_MILLIS,
            p95=metrics_df["ttlt_ns"].quantile(0.95) / NANOS_PER_MILLIS,
            p99=metrics_df["ttlt_ns"].quantile(0.99) / NANOS_PER_MILLIS,
            std=metrics_df["ttlt_ns"].std() / NANOS_PER_MILLIS,
            streaming_only=False,
        )

        itl_record = Record(
            name="Inter Token Latency",
            unit="ms",
            avg=metrics_df["itl_ns"].mean() / NANOS_PER_MILLIS,
            min=metrics_df["itl_ns"].min() / NANOS_PER_MILLIS,
            max=metrics_df["itl_ns"].max() / NANOS_PER_MILLIS,
            p1=metrics_df["itl_ns"].quantile(0.01) / NANOS_PER_MILLIS,
            p5=metrics_df["itl_ns"].quantile(0.05) / NANOS_PER_MILLIS,
            p25=metrics_df["itl_ns"].quantile(0.25) / NANOS_PER_MILLIS,
            p50=metrics_df["itl_ns"].quantile(0.50) / NANOS_PER_MILLIS,
            p75=metrics_df["itl_ns"].quantile(0.75) / NANOS_PER_MILLIS,
            p90=metrics_df["itl_ns"].quantile(0.90) / NANOS_PER_MILLIS,
            p95=metrics_df["itl_ns"].quantile(0.95) / NANOS_PER_MILLIS,
            p99=metrics_df["itl_ns"].quantile(0.99) / NANOS_PER_MILLIS,
            std=metrics_df["itl_ns"].std() / NANOS_PER_MILLIS,
            streaming_only=True,
        )

        # Create and return ProfileResultsMessage
        return ProfileResultsMessage(
            service_id=self.service_id,
            records=[ttft_record, ttlt_record, itl_record],
        )


def main() -> None:
    """Main entry point for the records manager."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(RecordsManager)


if __name__ == "__main__":
    sys.exit(main())

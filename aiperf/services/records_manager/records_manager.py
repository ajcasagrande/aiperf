# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import sys

import pandas as pd

from aiperf.common.comms.client_enums import ClientType, PullClientType
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.constants import NANOS_PER_MILLIS
from aiperf.common.data_exporter.record import Record
from aiperf.common.enums import CommandType, MessageType, ServiceType, Topic
from aiperf.common.factories import ServiceFactory
from aiperf.common.hooks import (
    on_cleanup,
    on_configure,
    on_init,
    on_start,
    on_stop,
)
from aiperf.common.messages import (
    CommandMessage,
    InferenceResultsMessage,
    Message,
    ProfileResultsMessage,
    ProfileStatsMessage,
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
        self.error_records: list[RequestErrorRecord | RequestRecord] = []

        # Track per-worker statistics
        self.worker_request_counts: dict[str, int] = {}
        self.worker_error_counts: dict[str, int] = {}

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
        self.register_command_callback(
            CommandType.PROCESS_RECORDS,
            self.process_records,
        )

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
        worker_id = message.service_id

        # Initialize worker counters if not seen before
        if worker_id not in self.worker_request_counts:
            self.worker_request_counts[worker_id] = 0
        if worker_id not in self.worker_error_counts:
            self.worker_error_counts[worker_id] = 0

        if isinstance(record, RequestErrorRecord):
            self.logger.warning(f"Received error inference results: {record}")
            self.error_records.append(record)
            self.worker_error_counts[worker_id] += 1

        elif isinstance(record, RequestRecord):
            if record.valid:
                self.logger.debug(
                    "Received inference results: %f milliseconds. %f milliseconds.",
                    record.time_to_first_response_ns / NANOS_PER_MILLIS,
                    record.time_to_last_response_ns / NANOS_PER_MILLIS,
                )
                self.records.append(record)
                self.worker_request_counts[worker_id] += 1

            else:
                self.logger.warning("Received invalid inference results: %s", record)
                self.error_records.append(record)
                self.worker_error_counts[worker_id] += 1

        else:
            self.logger.warning(
                f"Received unknown inference results type: {type(record)}"
            )
            self.error_records.append(record)
            self.worker_error_counts[worker_id] += 1

        await self.comms.publish(
            topic=Topic.PROFILE_STATS,
            message=ProfileStatsMessage(
                service_id=self.service_id,
                error_count=len(self.error_records),
                completed=len(self.records),
                worker_stats=self.worker_request_counts.copy(),
            ),
        )

    async def process_records(self, _: CommandMessage) -> None:
        """Process the records.

        This method is called when the records manager receives a command to process the records.
        """
        self.logger.debug("Processing records")
        # TODO: Implement records processing
        self.logger.info(
            "Processed %d successful records and %d error records",
            len(self.records),
            len(self.error_records),
        )

        profile_results = await self.post_process_records()
        self.logger.info("Profile results: %s", profile_results)

        if profile_results:
            await self.comms.publish(
                topic=Topic.PROFILE_RESULTS,
                message=profile_results,
            )
        else:
            self.logger.error("No profile results to publish")
            await self.comms.publish(
                topic=Topic.PROFILE_RESULTS,
                message=ProfileResultsMessage(
                    service_id=self.service_id,
                    records=[],
                ),
            )

    async def post_process_records(self) -> ProfileResultsMessage | None:
        """Post process the records."""
        self.logger.debug("Post processing records")

        if not self.records:
            self.logger.warning("No successful records to process")
            return None

        valid_records = [record for record in self.records if record.valid]
        # Extract time to first response values
        time_to_first_token_values = [
            record.time_to_first_response_ns for record in valid_records
        ]
        time_to_second_token_values = [
            record.time_to_second_response_ns for record in valid_records
        ]
        time_to_last_token_values = [
            record.time_to_last_response_ns for record in valid_records
        ]
        inter_token_latency_values = [
            record.inter_token_latency_ns for record in valid_records
        ]

        # Create single DataFrame with all metrics
        metrics_df = pd.DataFrame(
            {
                "ttft_ns": time_to_first_token_values,
                "ttst_ns": time_to_second_token_values,
                "ttlt_ns": time_to_last_token_values,
                "itl_ns": inter_token_latency_values,
            }
        )

        # Create Record objects (converting from ns to ms)
        ttft_record = record_from_dataframe(
            df=metrics_df,
            column_name="ttft_ns",
            name="Time to First Token",
            unit="ms",
            streaming_only=True,
        )

        ttst_record = record_from_dataframe(
            df=metrics_df,
            column_name="ttst_ns",
            name="Time to Second Token",
            unit="ms",
            streaming_only=True,
        )

        ttlt_record = record_from_dataframe(
            df=metrics_df,
            column_name="ttlt_ns",
            name="Time to Last Token",
            unit="ms",
            streaming_only=False,
        )

        itl_record = record_from_dataframe(
            df=metrics_df,
            column_name="itl_ns",
            name="Inter Token Latency",
            unit="ms",
            streaming_only=True,
        )

        # Create and return ProfileResultsMessage
        return ProfileResultsMessage(
            service_id=self.service_id,
            records=[ttft_record, ttst_record, ttlt_record, itl_record],
        )


def record_from_dataframe(
    df: pd.DataFrame,
    column_name: str,
    name: str,
    unit: str,
    streaming_only: bool,
) -> Record:
    """Create a Record from a DataFrame."""
    return Record(
        name=name,
        unit=unit,
        avg=df[column_name].mean() / NANOS_PER_MILLIS,
        min=df[column_name].min() / NANOS_PER_MILLIS,
        max=df[column_name].max() / NANOS_PER_MILLIS,
        p1=df[column_name].quantile(0.01) / NANOS_PER_MILLIS,
        p5=df[column_name].quantile(0.05) / NANOS_PER_MILLIS,
        p25=df[column_name].quantile(0.25) / NANOS_PER_MILLIS,
        p50=df[column_name].quantile(0.50) / NANOS_PER_MILLIS,
        p75=df[column_name].quantile(0.75) / NANOS_PER_MILLIS,
        p90=df[column_name].quantile(0.90) / NANOS_PER_MILLIS,
        p95=df[column_name].quantile(0.95) / NANOS_PER_MILLIS,
        p99=df[column_name].quantile(0.99) / NANOS_PER_MILLIS,
        std=df[column_name].std() / NANOS_PER_MILLIS,
        count=int(df[column_name].count()),
        streaming_only=streaming_only,
    )


def main() -> None:
    """Main entry point for the records manager."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(RecordsManager)


if __name__ == "__main__":
    sys.exit(main())

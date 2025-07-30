# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.constants import NANOS_PER_MILLIS
from aiperf.common.enums import CreditPhase, MessageType, MetricTag
from aiperf.common.hooks import background_task, on_message
from aiperf.common.messages import (
    CreditPhaseCompleteMessage,
    CreditPhaseProgressMessage,
    CreditPhaseStartMessage,
    MetricsPreviewMessage,
)
from aiperf.common.mixins import MessageBusClientMixin
from aiperf.common.models import CreditPhaseStats, MetricResult, ProfileResults


class ProgressLogger(MessageBusClientMixin):
    """Progress reporter to console."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.phase_stats: CreditPhaseStats = CreditPhaseStats(
            type=CreditPhase.PROFILING
        )
        self.metrics_preview: ProfileResults | None = None

    @on_message(MessageType.CREDIT_PHASE_START)
    async def _on_credit_phase_start(self, message: CreditPhaseStartMessage) -> None:
        if self.phase_stats.type != message.phase:
            return
        self.phase_stats.type = message.phase
        self.phase_stats.start_ns = message.start_ns
        self.phase_stats.total_expected_requests = message.total_expected_requests
        self.phase_stats.expected_duration_sec = message.expected_duration_sec

    @on_message(MessageType.CREDIT_PHASE_COMPLETE)
    async def _on_credit_phase_complete(
        self, message: CreditPhaseCompleteMessage
    ) -> None:
        if self.phase_stats.type != message.phase:
            return
        self.phase_stats.completed = message.completed
        self.phase_stats.end_ns = message.end_ns
        self.print_progress()

    @on_message(MessageType.CREDIT_PHASE_PROGRESS)
    async def _on_credit_phase_progress(
        self, message: CreditPhaseProgressMessage
    ) -> None:
        if self.phase_stats.type != message.phase:
            return
        self.phase_stats.completed = message.completed
        self.phase_stats.sent = message.sent
        # NOTE: We don't need to print the progress here because it will be printed at regular intervals

    @property
    def progress(self) -> float:
        return self.phase_stats.progress_percent or 0.0

    @background_task(
        immediate=False,
        interval=lambda self: self.service_config.progress_logging_interval,
    )
    async def _print_progress_task(self) -> None:
        """Print the progress of the credit phase."""
        if self.phase_stats.is_started:
            self.print_progress()

    def print_progress(self) -> None:
        # TODO: Add time based progress printing
        if self.phase_stats.is_request_count_based:
            self.info(
                f"Progress: {self.phase_stats.completed:8,} / {self.phase_stats.total_expected_requests:,} ({self.progress:4.1f}%)"
            )
        else:
            self.info(f"Progress: {self.progress:05.1f}%")

    @on_message(MessageType.METRICS_PREVIEW)
    async def _on_metrics_preview(self, message: MetricsPreviewMessage) -> None:
        self.metrics_preview = message.metrics_preview
        self.debug(lambda: f"Received metrics preview: {self.metrics_preview}")
        if not self.metrics_preview or not self.metrics_preview.records:
            return
        stat_types = ("min", "avg", "max")
        metrics: dict[str, dict[str, float | None]] = {
            stat_type: {
                metric.tag: getattr(metric, stat_type)
                for metric in self.metrics_preview.records
                if isinstance(metric, MetricResult)
            }
            for stat_type in stat_types
        }
        results: list[str] = []
        delimiter = " / "

        formatters = {
            MetricTag.TTFT: (lambda x: f"{x / NANOS_PER_MILLIS:.2f}", "ms"),
            MetricTag.TTST: (lambda x: f"{x / NANOS_PER_MILLIS:.2f}", "ms"),
            MetricTag.INTER_TOKEN_LATENCY: (
                lambda x: f"{x / NANOS_PER_MILLIS:.2f}",
                "ms",
            ),
            MetricTag.REQUEST_LATENCY: (lambda x: f"{x / NANOS_PER_MILLIS:.2f}", "ms"),
            MetricTag.ISL: (lambda x: f"{x:.1f}", "tokens"),
            MetricTag.OSL: (lambda x: f"{x:.1f}", "tokens"),
            MetricTag.OUTPUT_TOKEN_THROUGHPUT: (lambda x: f"{x:,.1f}", "tokens/s"),
        }

        for metric_tag in formatters:
            if metric_tag in metrics[stat_types[0]]:
                vals = [
                    formatters[metric_tag][0](metrics[stat_type][metric_tag])
                    for stat_type in stat_types
                ]
                results.append(
                    f"{metric_tag}: {delimiter.join(vals)} {formatters[metric_tag][1]}"
                )

        newline = "\n"
        self.info(
            f"Metrics Preview {stat_types}: {newline.join(results)} ({self.metrics_preview.completed:,} records)"
        )

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import sys
from datetime import datetime
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container
from textual.widget import Widget
from textual.widgets.data_table import ColumnKey, RowDoesNotExist, RowKey

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.metric_enums import MetricFlags, MetricUnitT
from aiperf.common.exceptions import MetricUnitError
from aiperf.common.models.record_models import MetricResult
from aiperf.metrics.base_metric import BaseMetric
from aiperf.metrics.metric_registry import MetricRegistry
from aiperf.ui.dashboard.custom_widgets import NonFocusableDataTable

_logger = AIPerfLogger(__name__)


class MetricsPreviewTable(Widget):
    DEFAULT_CSS = """
    MetricsPreviewTable {
        height: 1fr;
    }
    NonFocusableDataTable {
        height: 1fr;
    }
    """

    COLUMNS = ["Metric", "avg", "min", "max", "p99", "p90", "p75", "std"]  # fmt: skip

    def __init__(self, user_config: UserConfig) -> None:
        super().__init__()
        self.user_config = user_config
        self.data_table: NonFocusableDataTable | None = None
        self._columns_initialized = False
        self._column_keys: dict[str, ColumnKey] = {}
        self._metric_row_keys: dict[str, RowKey] = {}
        self.metrics: list[MetricResult] = []

    def compose(self) -> ComposeResult:
        self.data_table = NonFocusableDataTable(cursor_type="row", show_cursor=False)
        yield self.data_table

    def on_mount(self) -> None:
        if self.data_table and not self._columns_initialized:
            self._initialize_columns()
            if self.metrics:
                self.update(self.metrics)

    def _should_skip(self, metric: MetricResult) -> bool:
        """Determine if a metric should be skipped."""
        metric_class = MetricRegistry.get_class(metric.tag)
        if metric_class.has_flags(MetricFlags.ERROR_ONLY):
            return True
        return (
            metric_class.has_flags(MetricFlags.HIDDEN)
            and not self.user_config.output.show_internal_metrics
        )

    def _initialize_columns(self) -> None:
        """Initialize table columns."""
        for col in self.COLUMNS:
            self._column_keys[col] = self.data_table.add_column(  # type: ignore
                Text(col, justify="right")
            )
        self._columns_initialized = True

    def update(self, metrics: list[MetricResult]) -> None:
        """Update the metrics table."""
        self.metrics = metrics

        if not self.data_table or not self.data_table.is_mounted:
            return

        if not self._columns_initialized:
            self._initialize_columns()

        metrics = [
            metric
            for metric in sorted(
                metrics,
                key=lambda m: MetricRegistry.get_class(m.tag).display_order
                or sys.maxsize,
            )
            if not self._should_skip(metric)
        ]
        _logger.debug(lambda: f"Updating metrics table with {len(metrics)} metrics")
        for metric in metrics:
            row_cells = self._format_metric_row(metric)
            if metric.tag in self._metric_row_keys:
                row_key = self._metric_row_keys[metric.tag]
                try:
                    _ = self.data_table.get_row_index(row_key)
                    self._update_single_row(row_cells, row_key)
                    continue
                except RowDoesNotExist:
                    # Row doesn't exist, fall through to add as new
                    pass

            # Add new metric row
            row_key = self.data_table.add_row(*row_cells)
            self._metric_row_keys[metric.tag] = row_key

    def _update_single_row(self, row_cells: list[Text], row_key: RowKey) -> None:
        """Update a single row's cells."""
        for col_name, cell_value in zip(self.COLUMNS, row_cells, strict=True):
            try:
                self.data_table.update_cell(  # type: ignore
                    row_key, self._column_keys[col_name], cell_value, update_width=True
                )
            except Exception as e:
                _logger.warning(
                    f"Error updating cell {col_name} with value {cell_value}: {e!r}"
                )

    def _format_metric_row(self, metric: MetricResult) -> list[Text]:
        """Format worker data into table row cells."""
        metric_class = MetricRegistry.get_class(metric.tag)
        display_unit = metric_class.display_unit or metric_class.unit
        return [
            Text(
                f"{metric_class.header} ({display_unit})",
                style="bold cyan",
                justify="right",
            ),
            self._format_metric_value(metric.avg, display_unit, metric_class),
            self._format_metric_value(metric.min, display_unit, metric_class),
            self._format_metric_value(metric.max, display_unit, metric_class),
            self._format_metric_value(metric.p99, display_unit, metric_class),
            self._format_metric_value(metric.p90, display_unit, metric_class),
            self._format_metric_value(metric.p75, display_unit, metric_class),
            self._format_metric_value(metric.std, display_unit, metric_class),
        ]

    def _format_metric_value(
        self,
        value: Any | None,
        display_unit: MetricUnitT,
        metric_class: type[BaseMetric],
    ) -> Text:
        """Format a metric value."""
        if value is None:
            return Text("N/A", justify="right", style="dim")

        if display_unit != metric_class.unit:
            try:
                value = metric_class.unit.convert_to(display_unit, value)
            except MetricUnitError as e:
                _logger.warning(f"Error during unit conversion: {e}")

        if isinstance(value, datetime):
            value_str = value.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(value, int | float):
            value_str = f"{value:,.2f}"
        else:
            value_str = str(value)
        return Text(value_str, justify="right", style="green")


class MetricsPreviewDashboard(Container):
    DEFAULT_CSS = """
    MetricsPreviewDashboard {
        border: round $primary;
        border-title-color: $primary;
        border-title-style: bold;
        height: 1fr;
        layout: vertical;
        margin: 0 0 0 0;
        scrollbar-gutter: auto;
    }
    """

    def __init__(self, user_config: UserConfig) -> None:
        super().__init__()
        self.user_config = user_config
        self.metrics_table: MetricsPreviewTable | None = None
        self.metrics: list[MetricResult] = []
        self.border_title = "Metrics Preview"

    def compose(self) -> ComposeResult:
        self.metrics_table = MetricsPreviewTable(user_config=self.user_config)
        yield self.metrics_table

    def on_metrics_preview(self, metrics: list[MetricResult]) -> None:
        """Handle metrics updates."""
        self.metrics = metrics
        if self.metrics_table:
            self.metrics_table.update(metrics)

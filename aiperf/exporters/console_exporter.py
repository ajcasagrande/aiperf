# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from rich.console import Console
from rich.table import Table

from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import DataExporterType
from aiperf.common.enums.metric_enums import MetricFlags
from aiperf.common.factories import DataExporterFactory
from aiperf.common.models import MetricResult
from aiperf.common.protocols import DataExporterProtocol
from aiperf.exporters.exporter_config import ExporterConfig
from aiperf.metrics.metric_registry import MetricRegistry


@implements_protocol(DataExporterProtocol)
@DataExporterFactory.register(DataExporterType.CONSOLE)
class ConsoleExporter:
    """A class that exports data to the console"""

    STAT_COLUMN_KEYS = ["avg", "min", "max", "p99", "p90", "p75", "std", "count"]

    def __init__(self, exporter_config: ExporterConfig) -> None:
        self._results = exporter_config.results
        self._endpoint_type = exporter_config.input_config.endpoint.type

    async def export(self, width: int | None = None) -> None:
        table = Table(title=self._get_title(), width=width)
        table.add_column("Metric", justify="right", style="cyan")
        for key in self.STAT_COLUMN_KEYS:
            table.add_column(key, justify="right", style="green")
        self._construct_table(table, self._results.records)

        console = Console()
        console.print("\n")
        console.print(table)
        if self._results.was_cancelled:
            console.print("[red][bold]Profile run was cancelled early[/bold][/red]")
        console.file.flush()

    def _construct_table(self, table: Table, records: list[MetricResult]) -> None:
        for record in records:
            if self._should_skip(record):
                continue
            table.add_row(*self._format_row(record))

    def _should_skip(self, record: MetricResult) -> bool:
        return MetricRegistry.get_class(record.tag).has_flags(MetricFlags.HIDDEN)

    def _format_row(self, record: MetricResult) -> list[str]:
        metric_class = MetricRegistry.get_class(record.tag)
        display_unit = metric_class.display_unit or metric_class.unit
        row = [f"{record.header} ({display_unit})"]
        for stat in self.STAT_COLUMN_KEYS:
            value = getattr(record, stat, None)
            if value is not None and display_unit != metric_class.unit:
                # TODO: Should probably check that the units are compatible before converting.
                #       Although that would be better done as part of the __init_subclass__ method of BaseMetric.
                value = metric_class.unit.convert_to(display_unit, value)
            if value is None:
                value = "[dim]N/A[/dim]"
            elif value == int(value):
                value = f"{int(value):,}"
            else:
                value = f"{value:,.2f}"
            row.append(value)
        return row

    def _get_title(self) -> str:
        return f"NVIDIA AIPerf | {self._endpoint_type.metrics_title}"

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 36: Exporters System

## Overview

The AIPerf exporters system provides flexible, extensible data export capabilities. After benchmarks complete, results are exported to multiple formats—console output, CSV files, and JSON—through a unified architecture. This chapter explores the complete exporter system, from the manager orchestration to individual exporter implementations.

## Table of Contents

1. [Exporter Architecture](#exporter-architecture)
2. [ExporterManager](#exportermanager)
3. [Console Formatting](#console-formatting)
4. [CSV Export](#csv-export)
5. [JSON Export](#json-export)
6. [Display Units](#display-units)
7. [Factory Pattern](#factory-pattern)
8. [Protocol Design](#protocol-design)

## Exporter Architecture

Located at `/home/anthony/nvidia/projects/aiperf/aiperf/exporters/`:

```
exporters/
├── exporter_manager.py          # Orchestrates all exporters
├── exporter_config.py            # Configuration model
├── console_metrics_exporter.py   # Console output
├── csv_exporter.py               # CSV file export
├── json_exporter.py              # JSON file export
└── display_units_utils.py        # Unit conversion
```

## ExporterManager

The ExporterManager coordinates all export operations:

```python
class ExporterManager(AIPerfLoggerMixin):
    """Manages data export through all registered exporters."""

    def __init__(
        self,
        results: ProfileResults,
        input_config: UserConfig,
        service_config: ServiceConfig,
        **kwargs,
    ):
        self._results = results
        self._input_config = input_config
        self._service_config = service_config
        self._exporter_config = ExporterConfig(
            results=results,
            user_config=input_config,
            service_config=service_config,
        )

    async def export_data(self) -> None:
        """Export to all file exporters."""
        for exporter_type in DataExporterFactory.get_all_class_types():
            exporter = DataExporterFactory.create_instance(
                exporter_type,
                exporter_config=self._exporter_config
            )
            task = asyncio.create_task(exporter.export())
            self._tasks.add(task)
            task.add_done_callback(self._task_done_callback)

        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def export_console(self, console: Console) -> None:
        """Export to console."""
        for exporter_type in ConsoleExporterFactory.get_all_class_types():
            exporter = ConsoleExporterFactory.create_instance(
                exporter_type,
                exporter_config=self._exporter_config
            )
            await exporter.export(console=console)
```

## Console Formatting

ConsoleMetricsExporter displays results as Rich tables:

```python
@ConsoleExporterFactory.register(ConsoleExporterType.METRICS)
class ConsoleMetricsExporter(AIPerfLoggerMixin):
    """Export metrics to console as formatted table."""

    STAT_COLUMN_KEYS = ["avg", "min", "max", "p99", "p90", "p50", "std"]

    def get_renderable(self, records: list[MetricResult]) -> Table:
        """Generate Rich table from metrics."""
        table = Table(title="NVIDIA AIPerf | Metrics")
        table.add_column("Metric", justify="right", style="cyan")

        for key in self.STAT_COLUMN_KEYS:
            table.add_column(key, justify="right", style="green")

        for record in sorted(records, key=lambda x: x.tag):
            if self._should_show(record):
                table.add_row(*self._format_row(record))

        return table

    def _format_row(self, record: MetricResult) -> list[str]:
        """Format metric row."""
        row = [f"{record.header} ({record.unit})"]
        for stat in self.STAT_COLUMN_KEYS:
            value = getattr(record, stat, None)
            if value is None:
                row.append("[dim]N/A[/dim]")
            elif isinstance(value, (int, float)):
                row.append(f"{value:,.2f}")
            else:
                row.append(str(value))
        return row
```

## CSV Export

CSV exporter creates structured CSV files:

```python
@DataExporterFactory.register(DataExporterType.CSV)
class CsvExporter(AIPerfLoggerMixin):
    """Export metrics to CSV format."""

    async def export(self) -> None:
        """Export to CSV file."""
        self._output_directory.mkdir(parents=True, exist_ok=True)

        records = convert_all_metrics_to_display_units(
            self._results.records,
            self._metric_registry
        )

        csv_content = self._generate_csv_content(records)

        async with aiofiles.open(self._file_path, "w") as f:
            await f.write(csv_content)

    def _generate_csv_content(self, records: dict[str, MetricResult]) -> str:
        """Generate CSV content."""
        buf = io.StringIO()
        writer = csv.writer(buf)

        request_metrics, system_metrics = self._split_metrics(records)

        # Request metrics section
        if request_metrics:
            writer.writerow(["Metric"] + list(STAT_KEYS))
            for tag, metric in sorted(request_metrics.items()):
                row = [self._format_metric_name(metric)]
                for stat in STAT_KEYS:
                    value = getattr(metric, stat, None)
                    row.append(self._format_number(value))
                writer.writerow(row)

        # System metrics section
        if system_metrics:
            writer.writerow([])  # Blank line
            writer.writerow(["Metric", "Value"])
            for tag, metric in sorted(system_metrics.items()):
                writer.writerow([
                    self._format_metric_name(metric),
                    self._format_number(metric.avg)
                ])

        return buf.getvalue()
```

## JSON Export

JSON exporter serializes complete results:

```python
@DataExporterFactory.register(DataExporterType.JSON)
class JsonExporter(AIPerfLoggerMixin):
    """Export complete results to JSON."""

    async def export(self) -> None:
        """Export to JSON file."""
        self._output_directory.mkdir(parents=True, exist_ok=True)

        start_time = datetime.fromtimestamp(self._results.start_ns / NANOS_PER_SECOND)
        end_time = datetime.fromtimestamp(self._results.end_ns / NANOS_PER_SECOND)

        converted_records = convert_all_metrics_to_display_units(
            self._results.records,
            self._metric_registry
        )

        export_data = JsonExportData(
            input_config=self._input_config,
            records=converted_records,
            was_cancelled=self._results.was_cancelled,
            error_summary=self._results.error_summary,
            start_time=start_time,
            end_time=end_time,
        )

        export_json = export_data.model_dump_json(indent=2, exclude_unset=True)

        async with aiofiles.open(self._file_path, "w") as f:
            await f.write(export_json)
```

## Display Units

Utility functions convert metrics to display units:

```python
def to_display_unit(metric: MetricResult, registry) -> MetricResult:
    """Convert metric to display unit."""
    metric_class = registry.get_class(metric.tag)

    if not metric_class.display_unit:
        return metric

    conversion_factor = _get_conversion_factor(
        metric_class.unit,
        metric_class.display_unit
    )

    # Convert all numeric fields
    converted = metric.model_copy()
    for field in ["avg", "min", "max", "p50", "p90", "p95", "p99", "std"]:
        value = getattr(converted, field, None)
        if value is not None and isinstance(value, (int, float)):
            setattr(converted, field, value * conversion_factor)

    converted.unit = metric_class.display_unit
    return converted

def convert_all_metrics_to_display_units(
    metrics: list[MetricResult],
    registry
) -> dict[str, MetricResult]:
    """Convert all metrics to display units."""
    return {
        metric.tag: to_display_unit(metric, registry)
        for metric in metrics
    }
```

## Factory Pattern

Exporters registered with factories:

```python
# Data exporters (file output)
@DataExporterFactory.register(DataExporterType.CSV)
class CsvExporter:
    pass

@DataExporterFactory.register(DataExporterType.JSON)
class JsonExporter:
    pass

# Console exporters (terminal output)
@ConsoleExporterFactory.register(ConsoleExporterType.METRICS)
class ConsoleMetricsExporter:
    pass

@ConsoleExporterFactory.register(ConsoleExporterType.ERRORS)
class ConsoleErrorExporter:
    pass
```

## Protocol Design

Exporters implement protocols:

```python
@runtime_checkable
class DataExporterProtocol(Protocol):
    """Protocol for file exporters."""

    async def export(self) -> None:
        """Export data to file."""
        ...

    def get_export_info(self) -> FileExportInfo:
        """Get export file information."""
        ...

@runtime_checkable
class ConsoleExporterProtocol(Protocol):
    """Protocol for console exporters."""

    async def export(self, console: Console) -> None:
        """Export data to console."""
        ...
```

## Key Takeaways

1. **ExporterManager** orchestrates all export operations
2. **Multiple formats** supported: console, CSV, JSON
3. **Async export** for non-blocking file operations
4. **Factory pattern** for exporter registration
5. **Protocol-based** interfaces ensure consistency
6. **Display units** automatically converted for readability
7. **Rich formatting** for beautiful console output
8. **Dual CSV format** handles both request and system metrics
9. **Complete JSON** export includes full configuration
10. **Error handling** with fallback and logging
11. **File management** with automatic directory creation
12. **Metric filtering** based on flags (INTERNAL, EXPERIMENTAL)

## Navigation

- Previous: [Chapter 35: Dashboard Implementation](chapter-35-dashboard-implementation.md)
- Next: [Chapter 37: Log Management](chapter-37-log-management.md)
- [Back to Index](INDEX.md)

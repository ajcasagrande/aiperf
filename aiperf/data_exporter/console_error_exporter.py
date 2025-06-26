# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from rich.console import Console
from rich.table import Table

from aiperf.common.config import EndPointConfig
from aiperf.common.enums import DataExporterType
from aiperf.common.factories import DataExporterFactory
from aiperf.common.models import ErrorDetailsCount, ProfileResultsMessage


@DataExporterFactory.register(DataExporterType.CONSOLE_ERROR)
class ConsoleErrorExporter:
    """A class that exports error data to the console"""

    def __init__(self, endpoint_config: EndPointConfig):
        self.endpoint_config = endpoint_config

    async def export(self, results: ProfileResultsMessage) -> None:
        console = Console()

        if len(results.errors_by_type) > 0:
            table = Table(title=self._get_title())
            table.add_column("Code", justify="right", style="yellow")
            table.add_column("Type", justify="right", style="yellow")
            table.add_column("Message", justify="left", style="yellow")
            table.add_column("Count", justify="right", style="yellow")
            self._construct_table(table, results.errors_by_type)

            console.print("\n")
            console.print(table)

        if results.was_cancelled:
            console.print("[red][bold]Profile run was cancelled early[/bold][/red]")

    def _construct_table(
        self, table: Table, errors_by_type: list[ErrorDetailsCount]
    ) -> None:
        for error_details_count in errors_by_type:
            table.add_row(*self._format_row(error_details_count))

    def _format_row(self, error_details_count: ErrorDetailsCount) -> list[str]:
        details = error_details_count.error_details
        count = error_details_count.count

        return [
            str(details.code) if details.code else "[dim]N/A[/dim]",
            str(details.type) if details.type else "[dim]N/A[/dim]",
            str(details.message),
            f"{count:,}",
        ]

    def _get_title(self) -> str:
        return "[bold][red]NVIDIA AIPerf | Error Summary[/red][/bold]"

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from aiperf.common.messages import CommandErrorResponse
from aiperf.common.messages.command_messages import CommandResponse
from aiperf.common.models.error_models import ErrorDetails


def extract_errors(
    responses: list[CommandResponse | ErrorDetails],
) -> list[CommandErrorResponse | ErrorDetails]:
    """Extract errors from a list of command responses."""
    return [
        response
        for response in responses
        if isinstance(response, CommandErrorResponse | ErrorDetails)
    ]


def display_command_errors(
    title: str, errors: list[CommandErrorResponse | ErrorDetails]
) -> None:
    """Display command errors to the user."""
    if not errors:
        return
    summary = []
    for error in errors:
        if isinstance(error, CommandErrorResponse):
            summary.append(
                Text.assemble(
                    Text("•", style="bold red"),
                    f" Service: {error.service_id}: Command: {error.command}\n",
                )
            )
            summary.append(
                Text.assemble(
                    Text(f"\t{error.error.type}:", style="bold red"),
                    f" {error.error.message}\n",
                )
            )
        else:
            summary.append(
                Text.assemble(
                    Text(f"• {error.type}:", style="bold red"), f" {error.message}\n"
                )
            )
    # Remove the trailing newline from the last summary item
    summary[-1]._text[-1] = summary[-1]._text[-1].rstrip("\n")
    console = Console()
    console.print(
        Panel(
            Text.assemble(*summary),
            border_style="bold red",
            title=f"Error: {title}",
            title_align="left",
        )
    )
    console.file.flush()


def display_startup_errors(startup_errors: list[dict]) -> None:
    """Display startup errors to the user after UI is stopped."""
    if not startup_errors:
        return

    console = Console()
    if console.width < 100:
        console.width = 100

    # Print a notice to help users understand they should read the errors
    console.print("\n" + "=" * 80, style="bold red")
    console.print(
        "STARTUP ERRORS DETECTED - Please read the errors below:", style="bold red"
    )
    console.print("=" * 80 + "\n", style="bold red")

    summary = []
    for error in startup_errors:
        service_type = error.get("service_type", "unknown")
        service_id = error.get("service_id", "unknown")
        error_info = error.get("error", {})
        stage = error_info.get("stage", "unknown")
        exception_type = error_info.get("exception_type", "Exception")
        message = error_info.get("message", "No message provided")
        process_alive = error.get("process_alive", False)

        summary.append(
            Text.assemble(
                Text("•", style="bold red"),
                f" Service: {service_type} ({service_id})\n",
            )
        )
        summary.append(
            Text.assemble(
                Text("\tStage:", style="bold cyan"),
                f" {stage}\n",
            )
        )
        summary.append(
            Text.assemble(
                Text("\tError:", style="bold red"),
                f" {exception_type}: {message}\n",
            )
        )
        summary.append(
            Text.assemble(
                Text("\tProcess Status:", style="bold yellow"),
                f" {'Running' if process_alive else 'Stopped'}\n",
            )
        )
        summary.append(Text("\n"))  # Add spacing between errors

    # Remove the trailing newlines from the last summary item
    if summary:
        summary[-1] = Text("")
        if len(summary) > 1:
            summary[-2]._text[-1] = summary[-2]._text[-1].rstrip("\n")

    console.print(
        Panel(
            Text.assemble(*summary),
            border_style="bold red",
            title="Startup Errors",
            title_align="left",
        )
    )
    console.file.flush()


def display_configuration_errors(configuration_errors: list) -> None:
    """Display configuration errors to the user after UI is stopped."""
    if not configuration_errors:
        return

    console = Console()
    if console.width < 100:
        console.width = 100

    # Print a notice to help users understand they should read the errors
    console.print("\n" + "=" * 80, style="bold red")
    console.print(
        "CONFIGURATION ERRORS DETECTED - Please read the errors below:",
        style="bold red",
    )
    console.print("=" * 80 + "\n", style="bold red")

    summary = []
    for error in configuration_errors:
        if hasattr(error, "service_id"):
            # CommandErrorResponse
            summary.append(
                Text.assemble(
                    Text("•", style="bold red"),
                    f" Service: {error.service_id}: Command: {error.command}\n",
                )
            )
            summary.append(
                Text.assemble(
                    Text(f"\t{error.error.type}:", style="bold red"),
                    f" {error.error.message}\n",
                )
            )
        else:
            # ErrorDetails
            summary.append(
                Text.assemble(
                    Text(f"• {error.type}:", style="bold red"), f" {error.message}\n"
                )
            )

    # Remove the trailing newline from the last summary item
    if summary:
        summary[-1]._text[-1] = summary[-1]._text[-1].rstrip("\n")

    console.print(
        Panel(
            Text.assemble(*summary),
            border_style="bold red",
            title="Configuration Errors",
            title_align="left",
        )
    )

    console.file.flush()

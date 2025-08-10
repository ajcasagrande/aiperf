# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from contextlib import AbstractContextManager
from typing import TYPE_CHECKING

# NOTE: Do as little imports as possible in this file to ensure the CLI is fast to start up

if TYPE_CHECKING:
    from rich.console import RenderableType


def warn_command_not_implemented(command: str) -> None:
    """Warn the user that the subcommand is not implemented."""
    raise_startup_error_and_exit(
        f"Command [bold]{command}[/bold] is not yet implemented",
        title="Not Implemented",
    )


def raise_startup_error_and_exit(
    message: "RenderableType",
    title: str = "Error",
    exit_code: int = 1,
) -> None:
    """Raise a startup error and exit the program.

    Args:
        message: The message to display. Can be a string or a rich renderable.
        title: The title of the error.
        exit_code: The exit code to use.
    """
    import sys

    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    console.print(
        Panel(
            renderable=message,
            title=title,
            title_align="left",
            border_style="bold red",
        )
    )

    sys.exit(exit_code)


class exit_on_error(AbstractContextManager):
    """Context manager that exits the program if an error occurs.

    Args:
        *exceptions: The exceptions to exit on. If no exceptions are provided, all exceptions will be caught.
        message: The message to display. Can be a string or a rich renderable. Will be formatted with the exception as `{e}`.
        text_color: The text color to use.
        title: The title of the error.
        exit_code: The exit code to use.
    """

    def __init__(
        self,
        *exceptions: type[BaseException],
        message: "RenderableType" = "{e}",
        title: str = "Error",
        exit_code: int = 1,
    ):
        self.message: RenderableType = message
        self.title: str = title
        self.exit_code: int = exit_code
        self.exceptions: tuple[type[BaseException], ...] = exceptions

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            return

        if (
            not self.exceptions
            and not isinstance(exc_value, (SystemExit | KeyboardInterrupt))
        ) or issubclass(exc_type, self.exceptions):
            message = (
                self.message.format(e=exc_value)
                if isinstance(self.message, str)
                else self.message
            )
            raise_startup_error_and_exit(
                message,
                title=self.title,
                exit_code=self.exit_code,
            )


def warn_cancelled_early() -> None:
    """Warn the user that the profile run was cancelled early."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    console = Console()
    console.print(
        Panel(
            Text(
                "The profile run was cancelled early. Results shown may be incomplete or inaccurate.",
                style="yellow",
            ),
            border_style="bold yellow",
            title="Warning: Profile Run Cancelled Early",
            title_align="left",
        )
    )
    console.file.flush()

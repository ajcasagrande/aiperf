#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Splash screen module for AIPerf application.

Displays a beautiful ASCII art logo with animated loading indicators.
"""

import asyncio
import itertools
import time
from collections.abc import Iterator

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.text import Text


class SplashScreen:
    """Terminal splash screen for AIPerf application."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize the splash screen.

        Args:
            console: Rich console instance to use for output.
        """
        self.console = console or Console()
        self._animation_running = False

    @property
    def ascii_logo(self) -> str:
        """ASCII art logo for AIPerf."""
        return """
     █████╗ ██╗██████╗ ███████╗██████╗ ███████╗
    ██╔══██╗██║██╔══██╗██╔════╝██╔══██╗██╔════╝
    ███████║██║██████╔╝█████╗  ██████╔╝█████╗
    ██╔══██║██║██╔═══╝ ██╔══╝  ██╔══██╗██╔══╝
    ██║  ██║██║██║     ███████╗██║  ██║██║
    ╚═╝  ╚═╝╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝
        """

    def _get_loading_spinner(self) -> Iterator[str]:
        """Get animated loading spinner characters."""
        return itertools.cycle(["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"])

    def _get_gradient_colors(self) -> list[str]:
        """Get gradient colors for the logo."""
        return ["bright_green", "green", "cyan", "bright_cyan", "blue", "bright_blue"]

    def _colorize_logo(self) -> Text:
        """Apply gradient coloring to the ASCII logo."""
        lines = self.ascii_logo.strip().split("\n")
        colored_text = Text()
        colors = self._get_gradient_colors()

        for i, line in enumerate(lines):
            color = colors[i % len(colors)]
            colored_text.append(line + "\n", style=color)

        return colored_text

    def display_static(self) -> None:
        """Display static splash screen."""
        self.console.clear()

        # Create the main logo
        logo_text = self._colorize_logo()

        # Create subtitle
        subtitle = Text("High-Performance AI Benchmarking System", style="dim cyan")

        # Create version info
        version_info = Text("Starting services...", style="dim white")

        # Combine all elements
        content = Text()
        content.append(logo_text)
        content.append("\n")
        content.append(subtitle)
        content.append("\n\n")
        content.append(version_info)

        # Create panel with border
        panel = Panel(
            Align.center(content),
            border_style="bright_green",
            padding=(1, 2),
            title="[bold bright_green]NVIDIA AIPerf[/bold bright_green]",
            title_align="center",
        )

        self.console.print(Align.center(panel))

    async def display_animated(self, duration: float = 3.0) -> None:
        """Display animated splash screen with loading indicator.

        Args:
            duration: How long to display the splash screen in seconds.
        """
        spinner = self._get_loading_spinner()
        self._animation_running = True
        start_time = time.time()

        try:
            while self._animation_running and (time.time() - start_time) < duration:
                self.console.clear()

                # Create the main logo
                logo_text = self._colorize_logo()

                # Create subtitle
                subtitle = Text(
                    "High-Performance AI Benchmarking System", style="dim cyan"
                )

                # Create animated loading indicator
                spinner_char = next(spinner)
                loading_text = Text(
                    f"{spinner_char} Starting services...", style="dim white"
                )

                # Combine all elements
                content = Text()
                content.append(logo_text)
                content.append("\n")
                content.append(subtitle)
                content.append("\n\n")
                content.append(loading_text)

                # Create panel with border
                panel = Panel(
                    Align.center(content),
                    border_style="bright_green",
                    padding=(1, 2),
                    title="[bold bright_green]NVIDIA AIPerf[/bold bright_green]",
                    title_align="center",
                )

                self.console.print(Align.center(panel))
                await asyncio.sleep(0.1)  # Animation speed

        except KeyboardInterrupt:
            self._animation_running = False

    def stop_animation(self) -> None:
        """Stop the splash screen animation."""
        self._animation_running = False

    def display_startup_complete(self) -> None:
        """Display completion message."""
        self.console.clear()

        # Create the main logo
        logo_text = self._colorize_logo()

        # Create subtitle
        subtitle = Text("High-Performance AI Benchmarking System", style="dim cyan")

        # Create completion message
        completion_text = Text(
            "✓ Services started successfully!", style="bold bright_green"
        )

        # Combine all elements
        content = Text()
        content.append(logo_text)
        content.append("\n")
        content.append(subtitle)
        content.append("\n\n")
        content.append(completion_text)

        # Create panel with border
        panel = Panel(
            Align.center(content),
            border_style="bright_green",
            padding=(1, 2),
            title="[bold bright_green]NVIDIA AIPerf[/bold bright_green]",
            title_align="center",
        )

        self.console.print(Align.center(panel))
        time.sleep(1)  # Brief pause to show completion


async def show_splash_screen(
    console: Console | None = None, duration: float = 3.0
) -> None:
    """Show the animated splash screen.

    Args:
        console: Rich console instance to use for output.
        duration: How long to display the splash screen in seconds.
    """
    splash = SplashScreen(console)
    await splash.display_animated(duration)


def show_static_splash_screen(console: Console | None = None) -> None:
    """Show the static splash screen.

    Args:
        console: Rich console instance to use for output.
    """
    splash = SplashScreen(console)
    splash.display_static()

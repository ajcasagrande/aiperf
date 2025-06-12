#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""Test script for the AIPerf splash screen."""

import asyncio

from rich.console import Console

from aiperf.ui.splash_screen import SplashScreen, show_splash_screen


async def main():
    """Test the splash screen functionality."""
    console = Console()

    print("Testing AIPerf Splash Screen...")
    print("=" * 50)

    # Test static splash screen
    print("\n1. Static splash screen:")
    input("Press Enter to continue...")
    splash = SplashScreen(console)
    splash.display_static()
    input("\nPress Enter to continue...")

    # Test animated splash screen
    print("\n2. Animated splash screen (3 seconds):")
    input("Press Enter to continue...")
    await show_splash_screen(console, duration=3.0)

    # Test completion screen
    print("\n3. Completion screen:")
    input("Press Enter to continue...")
    splash.display_startup_complete()

    print("\nAll tests completed!")


if __name__ == "__main__":
    asyncio.run(main())

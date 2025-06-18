#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Demo script for the new AIPerf Textual UI.

This script demonstrates the clean, minimalist Textual-based UI in action.
"""

import asyncio
import logging
import random
import time

from aiperf.common.models import (
    ProfileProgressMessage,
    ProfileResultsMessage,
    ProfileStatsMessage,
)
from aiperf.ui.textual_ui import AIPerfTextualUI


class DemoUI:
    """Demo class to simulate AIPerf UI usage."""

    def __init__(self):
        self.ui = AIPerfTextualUI()
        self.total_requests = 1000
        self.completed_requests = 0
        self.error_count = 0

    async def run_demo(self) -> None:
        """Run the UI demo."""
        try:
            # Initialize and start the UI
            await self.ui.initialize()
            await self.ui.start()

            # Simulate progress updates
            await self._simulate_progress()

        except KeyboardInterrupt:
            logging.info("Demo interrupted by user")
        finally:
            await self.ui.stop()

    async def _simulate_progress(self) -> None:
        """Simulate realistic progress updates."""
        start_time_ns = time.time_ns()

        # Generate some initial logs
        logging.info("Starting AIPerf demo simulation")
        logging.info(f"Total requests to process: {self.total_requests}")

        batch_count = 0
        while self.completed_requests < self.total_requests:
            # Simulate variable processing speed
            batch_size = random.randint(5, 25)
            self.completed_requests = min(
                self.completed_requests + batch_size, self.total_requests
            )
            batch_count += 1

            # Generate some informational logs
            if batch_count % 10 == 0:
                logging.info(
                    f"Processed batch {batch_count}, completed {self.completed_requests}/{self.total_requests} requests"
                )

            # Simulate occasional errors (1-3% error rate)
            if random.random() < 0.02:
                self.error_count += 1
                logging.warning(
                    f"Request error occurred (total errors: {self.error_count})"
                )

            # Simulate occasional warnings
            if random.random() < 0.01:
                logging.warning("High latency detected in current batch")

            # Send progress update
            progress_message = ProfileProgressMessage(
                service_id="demo-service",
                start_ns=start_time_ns,
                total=self.total_requests,
                completed=self.completed_requests,
            )
            self.ui.update_profile_progress(progress_message)

            # Send stats update
            stats_message = ProfileStatsMessage(
                service_id="demo-service",
                error_count=self.error_count,
                completed=self.completed_requests,
            )
            self.ui.update_profile_stats(stats_message)

            # Wait a bit before next update
            await asyncio.sleep(random.uniform(0.1, 0.3))

            # Generate completion logs
        logging.info("All requests completed successfully!")
        logging.info(
            f"Final stats: {self.completed_requests} completed, {self.error_count} errors"
        )

        if self.error_count > 0:
            error_rate = (self.error_count / self.completed_requests) * 100
            logging.warning(f"Error rate: {error_rate:.1f}%")
        else:
            logging.info("No errors encountered during processing")

        # Send final results
        results_message = ProfileResultsMessage(
            service_id="demo-service",
            total=self.total_requests,
            completed=self.completed_requests,
            records=[],  # Empty for demo
            errors_by_type=[],
            was_cancelled=False,
        )

        logging.info("Sending final results...")
        await self.ui.process_final_results(results_message)


async def main():
    """Main demo function."""
    logging.basicConfig(level=logging.INFO)

    print("🚀 AIPerf Textual UI Demo")
    print("=" * 50)
    print("This demo showcases the new clean, minimalist UI built with Textual.")
    print("Press 'q' or Ctrl+C to quit during the demo.")
    print()

    demo = DemoUI()
    await demo.run_demo()

    print("✨ Demo completed! Thank you for trying the new AIPerf Textual UI.")


if __name__ == "__main__":
    asyncio.run(main())

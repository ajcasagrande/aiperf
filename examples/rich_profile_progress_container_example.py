#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Example script demonstrating the RichProfileProgressContainer.

This script shows how to use the new Textual container that encapsulates
the Rich profile progress dashboard functionality.
"""

import asyncio
import random
import time

from textual.app import App, ComposeResult
from textual.containers import Vertical

from aiperf.common.enums import CreditPhase
from aiperf.progress.progress_tracker import ProfileRunProgress, ProgressTracker
from aiperf.ui.textual.rich_profile_progress_container import (
    RichProfileProgressContainer,
)


class ProfileProgressExampleApp(App):
    """Example application showcasing the RichProfileProgressContainer."""

    CSS = """
    Screen {
        background: $surface;
    }

    #main-container {
        height: 100%;
        padding: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.profile_container: RichProfileProgressContainer | None = None
        self.progress_tracker: ProgressTracker | None = None
        self.title = "Rich Profile Progress Container Example"
        self.simulation_running = False

    def compose(self) -> ComposeResult:
        """Compose the application layout."""
        with Vertical(id="main-container"):
            # Create progress tracker
            self.progress_tracker = ProgressTracker()

            # Create the container
            self.profile_container = RichProfileProgressContainer(
                progress_tracker=self.progress_tracker, show_phase_overview=True
            )
            yield self.profile_container

    async def on_mount(self) -> None:
        """Initialize the application with sample data."""
        if self.profile_container and self.progress_tracker:
            # Create sample profile run
            self._create_sample_profile_run()

            # Update the container with sample data
            self.profile_container.update_progress()

            # Start simulation
            self.simulation_running = True
            self.set_interval(1.0, self._update_simulation)

    def _create_sample_profile_run(self) -> None:
        """Create a sample profile run for demonstration."""
        if not self.progress_tracker:
            return

        # Create a profile run
        profile_run = ProfileRunProgress(
            profile_id="demo-profile-001",
            start_ns=time.time_ns() - 30_000_000_000,  # Started 30 seconds ago
            active_phase=CreditPhase.STEADY_STATE,
        )

        # Add some initial phase data
        from aiperf.common.credit_models import CreditPhaseStats, PhaseProcessingStats
        from aiperf.progress.progress_tracker import CreditPhaseComputedStats

        # Warmup phase (completed)
        warmup_stats = CreditPhaseStats(
            type=CreditPhase.WARMUP,
            start_ns=time.time_ns() - 30_000_000_000,
            end_ns=time.time_ns() - 20_000_000_000,
            total_requests=50,
            sent=50,
            completed=50,
        )
        profile_run.phases[CreditPhase.WARMUP] = warmup_stats

        # Steady state phase (in progress)
        steady_stats = CreditPhaseStats(
            type=CreditPhase.STEADY_STATE,
            start_ns=time.time_ns() - 20_000_000_000,
            total_requests=1000,
            sent=300,
            completed=250,
        )
        profile_run.phases[CreditPhase.STEADY_STATE] = steady_stats

        # Add computed stats for steady state
        computed_stats = CreditPhaseComputedStats(
            requests_per_second=12.5,
            requests_eta=60.0,
            records_per_second=11.8,
            records_eta=65.0,
        )
        profile_run.computed_stats[CreditPhase.STEADY_STATE] = computed_stats

        # Add processing stats
        processing_stats = PhaseProcessingStats(
            processed=240,
            errors=5,
        )
        profile_run.processing_stats[CreditPhase.STEADY_STATE] = processing_stats

        # Add some worker task stats
        from aiperf.common.worker_models import WorkerPhaseTaskStats

        profile_run.worker_task_stats = {
            "worker-001": {
                CreditPhase.STEADY_STATE: WorkerPhaseTaskStats(
                    total=100,
                    completed=85,
                    failed=2,
                )
            },
            "worker-002": {
                CreditPhase.STEADY_STATE: WorkerPhaseTaskStats(
                    total=100,
                    completed=80,
                    failed=1,
                )
            },
            "worker-003": {
                CreditPhase.STEADY_STATE: WorkerPhaseTaskStats(
                    total=100,
                    completed=75,
                    failed=3,
                )
            },
        }

        # Set the profile run in the tracker
        self.progress_tracker.current_profile_run = profile_run
        self.progress_tracker.active_credit_phase = CreditPhase.STEADY_STATE

    def _update_simulation(self) -> None:
        """Update simulation to show changing progress."""
        if (
            not self.simulation_running
            or not self.progress_tracker
            or not self.progress_tracker.current_profile_run
        ):
            return

        profile_run = self.progress_tracker.current_profile_run

        # Update steady state phase progress
        if CreditPhase.STEADY_STATE in profile_run.phases:
            phase_stats = profile_run.phases[CreditPhase.STEADY_STATE]

            # Simulate progress (don't exceed total)
            if phase_stats.completed < phase_stats.total_requests:
                # Randomly advance progress
                advance = random.randint(0, 3)
                phase_stats.completed = min(
                    phase_stats.completed + advance, phase_stats.total_requests
                )
                phase_stats.sent = min(
                    phase_stats.sent + advance, phase_stats.total_requests
                )

                # Check if phase is complete
                if phase_stats.completed >= phase_stats.total_requests:
                    phase_stats.end_ns = time.time_ns()
                    # Start cooldown phase
                    self._start_cooldown_phase()

        # Update processing stats
        if CreditPhase.STEADY_STATE in profile_run.processing_stats:
            processing_stats = profile_run.processing_stats[CreditPhase.STEADY_STATE]

            # Simulate processing progress
            if processing_stats.processed < 1000:
                advance = random.randint(0, 2)
                processing_stats.processed = min(
                    processing_stats.processed + advance, 1000
                )

                # Occasionally add an error
                if random.random() < 0.1:
                    processing_stats.errors += 1

        # Update computed stats (simulate changing rates)
        if CreditPhase.STEADY_STATE in profile_run.computed_stats:
            computed = profile_run.computed_stats[CreditPhase.STEADY_STATE]

            # Simulate fluctuating rates
            computed.requests_per_second = 12.5 + random.uniform(-2.0, 2.0)
            computed.records_per_second = 11.8 + random.uniform(-1.5, 1.5)

            # Update ETAs based on progress
            if CreditPhase.STEADY_STATE in profile_run.phases:
                phase_stats = profile_run.phases[CreditPhase.STEADY_STATE]
                remaining = phase_stats.total_requests - phase_stats.completed
                if computed.requests_per_second > 0:
                    computed.requests_eta = remaining / computed.requests_per_second
                else:
                    computed.requests_eta = None

        # Update worker task stats
        for worker_id, worker_phases in profile_run.worker_task_stats.items():
            if CreditPhase.STEADY_STATE in worker_phases:
                task_stats = worker_phases[CreditPhase.STEADY_STATE]

                # Simulate task progress
                if task_stats.completed < task_stats.total:
                    if random.random() < 0.3:  # 30% chance to complete a task
                        task_stats.completed += 1

                # Occasionally add a failure
                if random.random() < 0.02:  # 2% chance to fail a task
                    task_stats.failed += 1

        # Update the display
        if self.profile_container:
            self.profile_container.update_progress()

    def _start_cooldown_phase(self) -> None:
        """Start the cooldown phase."""
        if not self.progress_tracker or not self.progress_tracker.current_profile_run:
            return

        profile_run = self.progress_tracker.current_profile_run

        # Add cooldown phase
        from aiperf.common.credit_models import CreditPhaseStats, PhaseProcessingStats
        from aiperf.progress.progress_tracker import CreditPhaseComputedStats

        cooldown_stats = CreditPhaseStats(
            type=CreditPhase.COOLDOWN,
            start_ns=time.time_ns(),
            total_requests=100,
            sent=0,
            completed=0,
        )
        profile_run.phases[CreditPhase.COOLDOWN] = cooldown_stats

        # Switch to cooldown phase
        self.progress_tracker.active_credit_phase = CreditPhase.COOLDOWN

        # Add computed stats for cooldown
        computed_stats = CreditPhaseComputedStats(
            requests_per_second=5.0,
            requests_eta=20.0,
            records_per_second=4.8,
            records_eta=22.0,
        )
        profile_run.computed_stats[CreditPhase.COOLDOWN] = computed_stats

        # Add processing stats
        processing_stats = PhaseProcessingStats(
            processed=0,
            errors=0,
        )
        profile_run.processing_stats[CreditPhase.COOLDOWN] = processing_stats

    def on_key(self, event) -> None:
        """Handle key events."""
        if event.key == "q":
            self.exit()
        elif event.key == "p":
            # Toggle simulation
            self.simulation_running = not self.simulation_running
        elif event.key == "r":
            # Reset to initial state
            self._create_sample_profile_run()
            if self.profile_container:
                self.profile_container.update_progress()
        elif event.key == "o":
            # Toggle phase overview
            if self.profile_container:
                self.profile_container.toggle_phase_overview()
        elif event.key == "c":
            # Complete current phase
            if self.progress_tracker and self.progress_tracker.current_profile_run:
                profile_run = self.progress_tracker.current_profile_run
                active_phase = self.progress_tracker.active_credit_phase

                if active_phase and active_phase in profile_run.phases:
                    phase_stats = profile_run.phases[active_phase]
                    if phase_stats.total_requests:
                        phase_stats.completed = phase_stats.total_requests
                        phase_stats.sent = phase_stats.total_requests
                        phase_stats.end_ns = time.time_ns()

                if self.profile_container:
                    self.profile_container.update_progress()


async def main():
    """Main function to run the example application."""
    app = ProfileProgressExampleApp()
    await app.run_async()


if __name__ == "__main__":
    print("Rich Profile Progress Container Example")
    print("======================================")
    print()
    print("This example demonstrates the RichProfileProgressContainer,")
    print("a Textual container that encapsulates the Rich profile progress dashboard.")
    print()
    print("Controls:")
    print("  q - Quit")
    print("  p - Toggle simulation (pause/resume)")
    print("  r - Reset to initial state")
    print("  o - Toggle phase overview")
    print("  c - Complete current phase")
    print()
    print("The display updates automatically every second during simulation.")
    print()

    asyncio.run(main())

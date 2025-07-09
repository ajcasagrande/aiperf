# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Label, ProgressBar, Static

from aiperf.common.enums import CreditPhase
from aiperf.ui.base_widgets import InteractiveAIPerfWidget

if TYPE_CHECKING:
    from aiperf.progress.progress_tracker import ProgressTracker


class PhaseCard(Static):
    """A simple card widget representing a single credit phase."""

    DEFAULT_CSS = """
    PhaseCard {
        border: solid #444444;
        background: #2a2a2a;
        margin: 1 0;
        padding: 1;
        width: 100%;
        height: 6;
    }

    PhaseCard.active {
        border: solid #00d4aa;
        background: #333333;
    }

    PhaseCard.complete {
        border: solid #00ff00;
        background: #2a2a2a;
    }

    PhaseCard.pending {
        border: solid #666666;
        background: #222222;
    }

    PhaseCard .header {
        height: 1;
        color: #ffffff;
        text-style: bold;
    }

    PhaseCard .status {
        color: #888888;
        height: 1;
    }

    PhaseCard .progress-bar {
        height: 1;
        margin: 1 0;
    }

    PhaseCard .stats {
        layout: grid;
        grid-size: 2 1;
        grid-gutter: 1;
        height: 1;
    }

    PhaseCard .stat-value {
        color: #00d4aa;
        text-style: bold;
    }

    PhaseCard .stat-label {
        color: #888888;
    }

    PhaseCard.status-complete .status {
        color: #00ff00;
    }

    PhaseCard.status-active .status {
        color: #ffaa00;
    }

    PhaseCard.status-pending .status {
        color: #666666;
    }
    """

    def __init__(self, phase: CreditPhase, **kwargs) -> None:
        super().__init__(**kwargs)
        self.phase = phase
        self.phase_stats = None
        self.computed_stats = None
        self.is_active = False
        self.is_complete = False

    def compose(self) -> ComposeResult:
        """Compose the phase card."""
        with Vertical():
            # Header
            yield Label(
                f"{self.phase.value.replace('_', ' ').title()}", classes="header"
            )
            yield Label("Pending", id=f"status-{self.phase.value}", classes="status")

            # Progress bar
            yield ProgressBar(
                total=100, id=f"progress-{self.phase.value}", classes="progress-bar"
            )

            # Stats
            with Horizontal(classes="stats"):
                yield Label(
                    "0", id=f"completed-{self.phase.value}", classes="stat-value"
                )
                yield Label(
                    "0 req/s", id=f"rate-{self.phase.value}", classes="stat-value"
                )

    def update_phase_data(
        self, phase_stats=None, computed_stats=None, is_active=False
    ) -> None:
        """Update the phase card with current data."""
        self.phase_stats = phase_stats
        self.computed_stats = computed_stats
        self.is_active = is_active

        # Update card styling
        self.remove_class(
            "active",
            "complete",
            "pending",
            "status-active",
            "status-complete",
            "status-pending",
        )

        if phase_stats and phase_stats.is_complete:
            self.add_class("complete", "status-complete")
            self.is_complete = True
        elif is_active:
            self.add_class("active", "status-active")
        else:
            self.add_class("pending", "status-pending")

        # Update status, progress, and stats
        self._update_status()
        self._update_progress()
        self._update_stats()

    def _update_status(self) -> None:
        """Update the phase status text."""
        status_label = self.query_one(f"#status-{self.phase.value}", Label)

        if not self.phase_stats:
            status_label.update("Pending")
            return

        if self.phase_stats.is_complete:
            status_label.update("Complete")
        elif self.phase_stats.is_started:
            if self.is_active:
                status_label.update("Active")
            else:
                status_label.update("Running")
        else:
            status_label.update("Waiting")

    def _update_progress(self) -> None:
        """Update the progress bar."""
        progress_bar = self.query_one(f"#progress-{self.phase.value}", ProgressBar)

        if not self.phase_stats:
            progress_bar.update(progress=0)
            return

        if self.phase_stats.is_complete:
            progress_bar.update(progress=100)
        elif self.phase_stats.total and self.phase_stats.total > 0:
            progress = (self.phase_stats.completed / self.phase_stats.total) * 100
            progress_bar.update(progress=progress)
        else:
            progress_bar.update(progress=0)

    def _update_stats(self) -> None:
        """Update the statistics display."""
        # Update completed count
        completed_label = self.query_one(f"#completed-{self.phase.value}", Label)
        if self.phase_stats:
            if self.phase_stats.total:
                completed_label.update(
                    f"{self.phase_stats.completed}/{self.phase_stats.total}"
                )
            else:
                completed_label.update(f"{self.phase_stats.completed}")
        else:
            completed_label.update("0")

        # Update rate
        rate_label = self.query_one(f"#rate-{self.phase.value}", Label)
        if self.computed_stats and self.computed_stats.requests_per_second:
            rate = self.computed_stats.requests_per_second
            if rate >= 1000:
                rate_label.update(f"{rate / 1000:.1f}k/s")
            else:
                rate_label.update(f"{rate:.1f}/s")
        else:
            rate_label.update("0/s")

    def on_click(self, event) -> None:
        """Handle click events on the phase card."""
        # Send a message to the parent widget
        self.post_message(PhaseTimelineWidget.PhaseSelected(self.phase))


class PhaseTimelineWidget(InteractiveAIPerfWidget):
    """Clean timeline widget showing the progress of all credit phases."""

    DEFAULT_CSS = """
    PhaseTimelineWidget {
        border: solid #76b900;
        background: #1a1a1a;
        height: 100%;
    }

    PhaseTimelineWidget .header {
        background: #76b900;
        color: #000000;
        text-style: bold;
        padding: 0 1;
        dock: top;
        height: 3;
    }

    PhaseTimelineWidget .summary {
        background: #333333;
        border: solid #444444;
        padding: 1;
        margin: 1;
        height: 3;
    }

    PhaseTimelineWidget .phase-list {
        padding: 1;
        height: 100%;
    }
    """

    class PhaseSelected(Message):
        """Message sent when a phase is selected."""

        def __init__(self, phase: CreditPhase) -> None:
            super().__init__()
            self.phase = phase

    widget_title = "Phase Timeline"

    def __init__(self, progress_tracker: "ProgressTracker", **kwargs) -> None:
        super().__init__(progress_tracker, **kwargs)
        self.phase_cards = {}

    def compose(self) -> ComposeResult:
        """Compose the phase timeline widget."""
        with Vertical():
            # Header
            with Vertical(classes="header"):
                yield Label("Phase Timeline", classes="title")
                yield Label("", id="timeline-summary", classes="summary-text")

            # Summary section
            with Vertical(classes="summary"):
                yield Label("No active profile", id="summary-info")

            # Phase list
            with Vertical(classes="phase-list"):
                for phase in CreditPhase:
                    card = PhaseCard(phase, id=f"phase-{phase.value}")
                    self.phase_cards[phase] = card
                    yield card

    def update_content(self) -> None:
        """Update the phase timeline with current progress."""
        if not self.progress_tracker or not self.progress_tracker.current_profile_run:
            self._update_empty_state()
            return

        profile_run = self.progress_tracker.current_profile_run
        active_phase = self.progress_tracker.active_credit_phase

        # Update summary
        self._update_summary(profile_run, active_phase)

        # Update phase cards
        for phase in CreditPhase:
            phase_stats = profile_run.phases.get(phase)
            computed_stats = profile_run.computed_stats.get(phase)
            is_active = phase == active_phase

            if phase in self.phase_cards:
                self.phase_cards[phase].update_phase_data(
                    phase_stats=phase_stats,
                    computed_stats=computed_stats,
                    is_active=is_active,
                )

    def _update_empty_state(self) -> None:
        """Update widget when no profile run is active."""
        summary_label = self.query_one("#summary-info", Label)
        summary_label.update("No active profile")

        timeline_summary = self.query_one("#timeline-summary", Label)
        timeline_summary.update("System ready")

        # Reset all phase cards
        for card in self.phase_cards.values():
            card.update_phase_data(
                phase_stats=None, computed_stats=None, is_active=False
            )

    def _update_summary(self, profile_run, active_phase: CreditPhase | None) -> None:
        """Update the summary information."""
        summary_label = self.query_one("#summary-info", Label)
        timeline_summary = self.query_one("#timeline-summary", Label)

        if profile_run.is_complete:
            summary_label.update("Profile completed successfully")
            timeline_summary.update("All phases complete")
        elif profile_run.is_started:
            if active_phase:
                phase_name = active_phase.value.replace("_", " ").title()
                summary_label.update(f"Running: {phase_name}")

                # Calculate overall progress
                completed_phases = sum(
                    1 for p in profile_run.phases.values() if p.is_complete
                )
                total_phases = len(CreditPhase)
                progress_pct = (completed_phases / total_phases) * 100

                timeline_summary.update(
                    f"Progress: {progress_pct:.1f}% ({completed_phases}/{total_phases} phases)"
                )
            else:
                summary_label.update("Profile running")
                timeline_summary.update("Preparing phases...")
        else:
            summary_label.update("Profile initializing")
            timeline_summary.update("Waiting to start...")

    def on_click(self, event) -> None:
        """Handle click events on the widget."""
        # Let the phase cards handle their own clicks
        pass

    def on_phase_selected(self, message: PhaseSelected) -> None:
        """Handle phase selection."""
        # Focus on the selected phase or show more details
        self.notify(f"Selected phase: {message.phase.value}")

    def action_focus_active_phase(self) -> None:
        """Focus on the currently active phase."""
        if self.progress_tracker and self.progress_tracker.active_credit_phase:
            active_phase = self.progress_tracker.active_credit_phase
            if active_phase in self.phase_cards:
                self.phase_cards[active_phase].focus()

    def get_phase_duration(self, phase: CreditPhase) -> float | None:
        """Get the duration of a specific phase."""
        if not self.progress_tracker or not self.progress_tracker.current_profile_run:
            return None

        profile_run = self.progress_tracker.current_profile_run
        if phase not in profile_run.phases:
            return None

        phase_stats = profile_run.phases[phase]
        return phase_stats.elapsed_time if phase_stats.is_started else None

# # SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# # SPDX-License-Identifier: Apache-2.0

# from rich.align import Align
# from rich.console import RenderableType
# from rich.progress import (
#     BarColumn,
#     MofNCompleteColumn,
#     Progress,
#     SpinnerColumn,
#     TaskID,
#     TaskProgressColumn,
#     TextColumn,
#     TimeElapsedColumn,
#     TimeRemainingColumn,
# )
# from rich.table import Table
# from rich.text import Text
# from textual.app import ComposeResult
# from textual.containers import Container
# from textual.widgets import Static

# from aiperf.common.enums import CreditPhase
# from aiperf.common.utils import format_duration


# class ProgressDashboard(Container):
#     """Simple textual widget that displays Rich progress bars for profile execution."""

#     DEFAULT_CSS = """
#     ProgressDashboard {
#         height: 1fr;
#         border: round $primary;
#         border-title-color: $primary;
#         border-title-style: bold;
#         padding: 0 1 0 1;
#     }

#     #status-display {
#         height: auto;
#         margin: 0 1 0 1;
#     }

#     #progress-display {
#         height: auto;
#         margin: 0 1 0 1;
#     }

#     #stats-display {
#         height: auto;
#     }

#     #no-stats-message {
#         height: 1fr;
#         content-align: center middle;
#         color: $warning;
#         text-style: italic;
#     }
#     """

#     def __init__(self) -> None:
#         super().__init__()
#         self.border_title = "Profile Progress"

#         self.progress = Progress(
#             SpinnerColumn(),
#             TextColumn("[progress.description]{task.description}"),
#             BarColumn(),
#             TaskProgressColumn(),
#             MofNCompleteColumn(),
#             TimeElapsedColumn(),
#             TimeRemainingColumn(),
#             expand=True,
#         )

#         self.warmup_task_id: TaskID | None = None
#         self.profiling_task_id: TaskID | None = None
#         self.processing_task_id: TaskID | None = None

#         # self.status_widget: Static | None = None
#         self.progress_widget: Static | None = None
#         self.stats_widget: Static | None = None

#     def compose(self) -> ComposeResult:
#         # self.status_widget = Static(self._get_status_text(), id="status-display")
#         self.progress_widget = Static(self.progress, id="progress-display")
#         self.stats_widget = Static(self._get_stats_table(), id="stats-display")

#         # yield self.status_widget
#         yield self.progress_widget
#         yield self.stats_widget

#     def set_progress_tracker(self) -> None:
#         """Set the progress tracker and reset progress bars."""
#         self._reset_progress_bars()
#         self.update_display()

#     def update_display(self) -> None:
#         """Update the progress display."""
#         if not self.progress_widget or not self.stats_widget:
#             return

#         # Update status text
#         # self.status_widget.update(self._get_status_text())

#         # Update progress bars
#         self._update_progress_bars()

#         # Update statistics table
#         self.stats_widget.update(self._get_stats_table())

#         # # Update border title
#         # if self.progress_tracker and self.progress_tracker.current_profile_run:
#         #     profile_id = self.progress_tracker.current_profile_run.profile_id
#         #     self.border_title = f"Profile Progress: {profile_id or 'Unknown'}"
#         # else:
#         #     self.border_title = "Profile Progress"

#     # def _get_status_text(self) -> RenderableType:
#     #     """Get current status as Rich text."""
#     #     if not self.progress_tracker or not self.progress_tracker.current_profile_run:
#     #         return Text("Waiting for profile run...", style="dim yellow")

#     #     profile = self.progress_tracker.current_profile_run

#     #     if profile.is_complete:
#     #         return Text("Profile complete", style="bold green")
#     #     elif profile.is_started:
#     #         active_phase = self.progress_tracker.active_phase
#     #         if active_phase:
#     #             return Text(f"Running {active_phase.value}", style="bold cyan")
#     #         return Text("Running", style="bold yellow")
#     #     else:
#     #         return Text("Preparing...", style="dim")

#     def _update_progress_bars(self) -> None:
#         """Update progress bars based on current tracker state."""

#         # Handle warmup phase
#         if CreditPhase.WARMUP in profile.phase_infos:
#             warmup_phase = profile.phase_infos[CreditPhase.WARMUP]
#             if self.warmup_task_id is None and warmup_phase.total_expected_requests:
#                 self.warmup_task_id = self.progress.add_task(
#                     "Warmup requests", total=warmup_phase.total_expected_requests
#                 )
#             elif self.warmup_task_id is not None:
#                 self.progress.update(
#                     self.warmup_task_id, completed=warmup_phase.completed or 0
#                 )
#                 if warmup_phase.is_complete:
#                     self.progress.update(
#                         self.warmup_task_id,
#                         description="[green]Warmup complete[/green]",
#                     )

#         # Handle profiling phase
#         if CreditPhase.PROFILING in profile.phase_infos:
#             profiling_phase = profile.phase_infos[CreditPhase.PROFILING]
#             if (
#                 self.profiling_task_id is None
#                 and profiling_phase.total_expected_requests
#             ):
#                 self.profiling_task_id = self.progress.add_task(
#                     "Profiling requests", total=profiling_phase.total_expected_requests
#                 )
#             elif self.profiling_task_id is not None:
#                 self.progress.update(
#                     self.profiling_task_id, completed=profiling_phase.completed or 0
#                 )
#                 if profiling_phase.is_complete:
#                     self.progress.update(
#                         self.profiling_task_id,
#                         description="[green]Profiling complete[/green]",
#                     )

#             # Add processing progress for profiling phase
#             if (
#                 self.processing_task_id is None
#                 and profiling_phase.total_expected_requests
#                 and profiling_phase.is_started
#             ):
#                 self.processing_task_id = self.progress.add_task(
#                     "Processing results", total=profiling_phase.total_expected_requests
#                 )
#             elif self.processing_task_id is not None:
#                 self.progress.update(
#                     self.processing_task_id, completed=profiling_phase.processed or 0
#                 )
#                 if (
#                     profiling_phase.is_complete
#                     and profiling_phase.processed
#                     == profiling_phase.total_expected_requests
#                 ):
#                     self.progress.update(
#                         self.processing_task_id,
#                         description="[green]Processing complete[/green]",
#                     )

#         # Refresh the progress widget
#         if self.progress_widget:
#             self.progress_widget.update(self.progress)

#     def _get_stats_table(self) -> RenderableType:
#         """Create a statistics table similar to the rich version."""
#         if not self.progress_tracker or not self.progress_tracker.current_profile_run:
#             return Align(
#                 Text("No profile data available", style="bold italic orange"),
#                 align="center",
#             )

#         profile = self.progress_tracker.current_profile_run

#         # Get current phase for detailed stats
#         current_phase = None
#         phase_stats = None
#         if self.progress_tracker.active_phase:
#             current_phase = self.progress_tracker.active_phase
#             if current_phase in profile.phase_infos:
#                 phase_stats = profile.phase_infos[current_phase]

#         if not phase_stats:
#             return Align(
#                 Text("No profile data available", style="bold italic orange"),
#                 align="center",
#             )

#         # Create table with padding (same as rich version)
#         stats_table = Table.grid(padding=(0, 1, 0, 0))
#         stats_table.add_column(style="bold cyan", justify="right")
#         stats_table.add_column(style="bold white")

#         # Status
#         if phase_stats.is_complete:
#             status = Text("Complete", style="bold green")
#         else:
#             status = Text("Processing", style="bold yellow")

#         # Error calculations
#         error_percent = 0.0
#         if phase_stats.processed and phase_stats.processed > 0:
#             error_percent = (phase_stats.errors or 0) / phase_stats.processed * 100

#         error_color = (
#             "green" if error_percent == 0 else "red" if error_percent > 10 else "yellow"
#         )

#         # Add rows to table
#         stats_table.add_row("Status:", status)

#         # Progress information
#         if phase_stats.total_expected_requests:
#             progress_percent = (
#                 (phase_stats.sent or 0) / phase_stats.total_expected_requests * 100
#             )
#             stats_table.add_row(
#                 "Progress:",
#                 f"{phase_stats.sent or 0:,} / {phase_stats.total_expected_requests:,} requests "
#                 f"({progress_percent:.1f}%)",
#             )

#         # Error information
#         stats_table.add_row(
#             "Errors:",
#             f"[{error_color}]{phase_stats.errors or 0:,} / {phase_stats.processed or 0:,} ({error_percent:.1f}%)[/{error_color}]",
#         )

#         # Rates
#         stats_table.add_row(
#             "Request Rate:", f"{phase_stats.records_per_second or 0:.1f} req/s"
#         )
#         stats_table.add_row(
#             "Processing Rate:", f"{phase_stats.records_per_second or 0:.1f} req/s"
#         )

#         # Timing information
#         stats_table.add_row("Elapsed:", format_duration(phase_stats.elapsed_time))
#         stats_table.add_row("Request ETA:", format_duration(phase_stats.requests_eta))
#         stats_table.add_row("Results ETA:", format_duration(phase_stats.records_eta))

#         return stats_table

#     def _reset_progress_bars(self) -> None:
#         """Reset all progress bars."""
#         if self.warmup_task_id is not None:
#             self.progress.remove_task(self.warmup_task_id)
#             self.warmup_task_id = None

#         if self.profiling_task_id is not None:
#             self.progress.remove_task(self.profiling_task_id)
#             self.profiling_task_id = None

#         if self.processing_task_id is not None:
#             self.progress.remove_task(self.processing_task_id)
#             self.processing_task_id = None

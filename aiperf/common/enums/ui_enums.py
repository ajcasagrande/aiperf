# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from functools import cached_property

from aiperf.common.enums.base_enums import (
    BasePydanticBackedStrEnum,
    BasePydanticEnumInfo,
)


class AIPerfUIInfo(BasePydanticEnumInfo):
    """Information about the UI."""

    is_dashboard: bool
    """Whether the UI is a dashboard."""
    description: str
    """The description of the UI."""


class AIPerfUIType(BasePydanticBackedStrEnum):
    """The type of UI to use."""

    RICH = AIPerfUIInfo(
        tag="rich",
        is_dashboard=True,
        description="Rich-based UI Dashboard. Requires the `rich` package to be installed. Clean, simple, and easy to use.",
    )
    TEXTUAL = AIPerfUIInfo(
        tag="textual",
        is_dashboard=True,
        description="Textual-based UI Dashboard. Requires the `textual` package to be installed. Full feature terminal UI with scrolling and mouse support.",
    )
    TQDM = AIPerfUIInfo(
        tag="tqdm",
        is_dashboard=False,
        description="No dashboard, just simple progress bars using `tqdm`. Requires the `tqdm` package to be installed.",
    )
    LOG = AIPerfUIInfo(
        tag="log",
        is_dashboard=False,
        description="Logs progress to the console as log messages.",
    )
    NONE = AIPerfUIInfo(
        tag="none",
        is_dashboard=False,
        description="No UI. This can be considered a fallback for when no other UI is available.",
    )

    @cached_property
    def info(self) -> AIPerfUIInfo:
        """Get the info for the UI."""
        return self._info  # type: ignore

    @property
    def is_dashboard(self) -> bool:
        """Check if the UI is a dashboard. This is for convenience to determine how to handle log queues."""
        return self.info.is_dashboard

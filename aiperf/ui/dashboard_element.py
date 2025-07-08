# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from typing import ClassVar

from rich.align import Align, AlignMethod
from rich.console import RenderableType
from rich.panel import Panel
from rich.style import StyleType
from rich.text import Text


class DashboardElement(ABC):
    """Base class for dashboard elements."""

    key: ClassVar[str]
    title: ClassVar[Text | str | None] = None
    border_style: ClassVar[StyleType | None] = None
    title_align: ClassVar[AlignMethod] = "center"
    height: ClassVar[int | None] = None
    width: ClassVar[int | None] = None
    expand: ClassVar[bool] = True

    @abstractmethod
    def get_content(self) -> RenderableType:
        """Get the content for the dashboard element."""
        raise NotImplementedError("Subclasses must implement get_content")

    def get_panel(self) -> Panel:
        """Get the panel for the dashboard element."""
        return Panel(
            self.get_content(),
            title=self.title,
            border_style=self.border_style if self.border_style else "none",
            title_align=self.title_align,
            height=self.height,
            width=self.width,
            expand=self.expand,
        )


class HeaderElement(DashboardElement):
    """Header element for the dashboard."""

    key = "header"
    border_style = "bright_green"

    def get_content(self) -> RenderableType:
        """Get the content for the header element."""
        return Align.center(Text("NVIDIA AIPerf Dashboard", style="bold bright_green"))

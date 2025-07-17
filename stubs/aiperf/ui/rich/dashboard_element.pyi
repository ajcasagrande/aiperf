#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import abc
from abc import ABC, abstractmethod
from typing import ClassVar

from rich.align import AlignMethod as AlignMethod
from rich.console import RenderableType as RenderableType
from rich.panel import Panel
from rich.style import StyleType as StyleType
from rich.text import Text

class DashboardElement(ABC, metaclass=abc.ABCMeta):
    key: ClassVar[str]
    title: ClassVar[Text | str | None]
    border_style: ClassVar[StyleType | None]
    title_align: ClassVar[AlignMethod]
    height: ClassVar[int | None]
    width: ClassVar[int | None]
    expand: ClassVar[bool]
    @abstractmethod
    def get_content(self) -> RenderableType: ...
    def get_panel(self) -> Panel: ...

class HeaderElement(DashboardElement):
    key: str
    border_style: str
    def get_content(self) -> RenderableType: ...

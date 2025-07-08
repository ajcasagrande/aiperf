# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for dashboard element components.
"""

import pytest
from rich.align import Align
from rich.panel import Panel
from rich.text import Text

from aiperf.ui.dashboard_element import DashboardElement, HeaderElement


class TestDashboardElementBase:
    """Test the DashboardElement base class."""

    def test_dashboard_element_is_abstract(self):
        """Test that DashboardElement cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            DashboardElement()

    def test_dashboard_element_subclass_requires_get_content(self):
        """Test that subclasses must implement get_content method."""

        class IncompleteElement(DashboardElement):
            key = "incomplete"

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteElement()

    def test_dashboard_element_subclass_with_get_content(self):
        """Test that subclasses with get_content can be instantiated."""

        class CompleteElement(DashboardElement):
            key = "complete"
            title = "Complete Element"
            border_style = "blue"

            def get_content(self):
                return "Test content"

        element = CompleteElement()
        assert element.key == "complete"
        assert element.title == "Complete Element"
        assert element.border_style == "blue"

    def test_dashboard_element_default_class_vars(self):
        """Test default class variable values."""

        class TestElement(DashboardElement):
            key = "test"

            def get_content(self):
                return "content"

        element = TestElement()
        assert element.title is None
        assert element.border_style is None
        assert element.title_align == "center"
        assert element.height is None
        assert element.width is None
        assert element.expand is True

    def test_dashboard_element_custom_class_vars(self):
        """Test custom class variable values."""

        class CustomElement(DashboardElement):
            key = "custom"
            title = Text("Custom Title", style="bold")
            border_style = "red"
            title_align = "left"
            height = 10
            width = 50
            expand = False

            def get_content(self):
                return "custom content"

        element = CustomElement()
        assert isinstance(element.title, Text)
        assert element.title.plain == "Custom Title"
        assert element.border_style == "red"
        assert element.title_align == "left"
        assert element.height == 10
        assert element.width == 50
        assert element.expand is False

    def test_get_panel_with_defaults(self, dashboard_element_instance):
        """Test get_panel with default settings."""
        panel = dashboard_element_instance.get_panel()

        assert isinstance(panel, Panel)
        assert panel.title == "Test Element"
        assert panel.border_style == "green"
        assert panel.title_align == "center"
        assert panel.expand is True

    def test_get_panel_with_no_border_style(self):
        """Test get_panel with no border style defaults to 'none'."""

        class NoBorderElement(DashboardElement):
            key = "no_border"
            title = "No Border"

            def get_content(self):
                return "content"

        element = NoBorderElement()
        panel = element.get_panel()

        assert panel.border_style == "none"

    def test_get_panel_with_custom_dimensions(self):
        """Test get_panel with custom dimensions."""

        class CustomDimensionElement(DashboardElement):
            key = "custom_dim"
            height = 20
            width = 80
            expand = False

            def get_content(self):
                return "content"

        element = CustomDimensionElement()
        panel = element.get_panel()

        assert panel.height == 20
        assert panel.width == 80
        assert panel.expand is False


class TestHeaderElement:
    """Test the HeaderElement implementation."""

    def test_header_element_initialization(self):
        """Test HeaderElement can be created."""
        header = HeaderElement()
        assert header.key == "header"
        assert header.border_style == "bright_green"

    def test_header_element_get_content(self):
        """Test HeaderElement get_content method."""
        header = HeaderElement()
        content = header.get_content()

        assert isinstance(content, Align)
        assert content.align == "center"

        text_content = content.renderable
        assert isinstance(text_content, Text)
        assert text_content.plain == "NVIDIA AIPerf Dashboard"
        assert "bold bright_green" in str(text_content.style)

    def test_header_element_get_panel(self):
        """Test HeaderElement get_panel method."""
        header = HeaderElement()
        panel = header.get_panel()

        assert isinstance(panel, Panel)
        assert panel.border_style == "bright_green"
        assert panel.title is None
        assert panel.title_align == "center"
        assert panel.expand is True

    def test_header_element_content_rendering(self):
        """Test that HeaderElement content renders correctly."""
        header = HeaderElement()
        content = header.get_content()

        assert isinstance(content, Align)
        text = content.renderable
        assert isinstance(text, Text)
        assert "NVIDIA AIPerf Dashboard" in text.plain
        assert "bold bright_green" in str(text.style)

    def test_header_element_class_variables(self):
        """Test HeaderElement class variables."""
        assert HeaderElement.key == "header"
        assert HeaderElement.border_style == "bright_green"
        assert HeaderElement.title is None
        assert HeaderElement.title_align == "center"
        assert HeaderElement.height is None
        assert HeaderElement.width is None
        assert HeaderElement.expand is True

#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from typing import Any


class BasePayloadParser(ABC):
    """Base class for all payload parsers."""

    @abstractmethod
    def parse_data_content(self, data_content: list[str]) -> list[str]:
        """Parse the data content from an SSE message into a list of strings to be tokenized."""
        pass

    @abstractmethod
    def parse_text_content(self, text_content: str) -> list[str]:
        """Parse text content from a server response message into a list of strings to be tokenized."""
        pass

    @abstractmethod
    def parse_raw_content(self, raw_content: Any) -> list[str]:
        """Parse raw content from a server response message into a list of strings to be tokenized."""
        pass


class BaseSSEPayloadParser(BasePayloadParser, ABC):
    """Base class for all SSE payload parsers."""

    def parse_data_content(self, data_content: list[str]) -> list[str]:
        """Parse the data content from an SSE message into a list of strings to be tokenized."""
        return [
            output for data in data_content for output in self.parse_text_content(data)
        ]

    def parse_raw_content(self, raw_content: Any) -> list[str]:
        """Parse raw content from a server response message into a list of strings to be tokenized."""
        if isinstance(raw_content, str):
            return self.parse_text_content(raw_content)
        elif isinstance(raw_content, list):
            return self.parse_data_content(raw_content)
        else:
            raise ValueError(f"Unsupported content type: {type(raw_content)}")

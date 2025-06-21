# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from aiperf.common.models import RequestRecord

logger = logging.getLogger(__name__)


class ResponseData(BaseModel):
    """Base class for all response data."""

    perf_ns: int = Field(description="The performance timestamp of the response.")
    raw_text: list[str] = Field(description="The raw text of the response.")
    parsed_text: list[str] = Field(description="The parsed text of the response.")
    metadata: dict[str, Any] = Field(description="The metadata of the response.")


class ResponseExtractor(ABC):
    """Base class for all response extractors."""

    @abstractmethod
    def extract_response_data(self, record: RequestRecord) -> list[ResponseData]:
        """Extract the text from a server response message."""

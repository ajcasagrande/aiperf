# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from typing import TYPE_CHECKING, Generic, Protocol, runtime_checkable

if TYPE_CHECKING:
    from aiperf.common.record_models import ParsedResponseRecord, ResponseData
from aiperf.common.record_models import (
    ParsedResponseRecord,
    ResponseData,
)
from aiperf.common.types import (
    InputT,
    OutputT,
)


################################################################################
# Post Processor Protocol
################################################################################
@runtime_checkable
class PostProcessorProtocol(Protocol, Generic[InputT, OutputT]):
    """
    PostProcessorProtocol is a protocol that defines the API for post-processors.
    It requires an `process` method that takes a list of records and returns a result.
    """

    async def process(self, records: dict) -> dict:
        """
        Execute the post-processing logic on the given records.

        :param records: The input data to be processed.
        :return: The processed data as a dictionary.
        """
        ...


################################################################################
# Data Exporter Protocol
################################################################################


@runtime_checkable
class DataExporterProtocol(Protocol):
    """
    Protocol for data exporters.
    Any class implementing this protocol must provide an `export` method
    that takes a list of Record objects and handles exporting them appropriately.
    """

    async def export(self) -> None:
        """Export the data."""
        ...


################################################################################
# Response Extractor Protocol
################################################################################


@runtime_checkable
class ResponseExtractor(Protocol):
    """Base class for all response extractors."""

    async def extract_response_data(
        self, record: ParsedResponseRecord
    ) -> list[ResponseData]:
        """Extract the text from a server response message."""
        ...

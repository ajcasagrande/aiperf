# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from typing import Generic, Protocol, runtime_checkable

from aiperf.common.record_models import (
    ParsedResponseRecord,
    ResponseData,
)
from aiperf.common.types import (
    ConfigT,
    InputT,
    OutputT,
    RequestT,
    ResponseT,
)

################################################################################
# Converter Protocols
################################################################################


@runtime_checkable
class InputConverterProtocol(Protocol, Generic[InputT, RequestT]):
    """Protocol for an input converter."""

    async def convert(self, input: InputT) -> RequestT:
        """Convert the input to the expected format."""
        ...


@runtime_checkable
class OutputConverterProtocol(Protocol, Generic[OutputT, ResponseT]):
    """Protocol for an output converter."""

    async def convert(self, output: OutputT) -> ResponseT:
        """Convert the output to the expected format."""
        ...


################################################################################
# Inference Server Client Protocols
################################################################################


@runtime_checkable
class InferenceClientProtocol(Protocol, Generic[ConfigT, RequestT]):
    """Protocol for an inference server client.

    This protocol defines the methods that must be implemented by any inference server client
    implementation that is compatible with the AIPerf framework.
    """

    # def __init__(self, client_config: ConfigT) -> None:
    #     """Create a new inference server client based on the provided configuration."""
    #     ...

    # @property
    # def client_config(self) -> ConfigT:
    #     """Get the client configuration."""
    #     ...

    # async def initialize(self) -> None:
    #     """Initialize the inference server client in an asynchronous context."""
    #     ...

    # async def format_payload(
    #     self, model_endpoint: ModelEndpointInfo, turn: Turn
    # ) -> RequestT:
    #     """Format the turn for the inference server."""
    #     ...

    # async def send_request(
    #     self,
    #     model_endpoint: ModelEndpointInfo,
    #     payload: RequestT,
    #     delayed: bool = False,
    # ) -> RequestRecord:
    #     """Send a request to the inference server.

    #     This method is used to send a request to the inference server.

    #     Args:
    #         model_endpoint: The endpoint to send the request to.
    #         payload: The payload to send to the inference server.
    #         delayed: Whether the request is delayed.
    #     Returns:
    #         The raw response from the inference server.
    #     """
    #     ...

    # async def close(self) -> None:
    #     """Close the client."""
    #     ...


################################################################################
# Post Processor Protocol
################################################################################


@runtime_checkable
class PostProcessorProtocol(Protocol):
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
class ResponseExtractorProtocol(Protocol):
    """Base class for all response extractors."""

    async def extract_response_data(
        self, record: ParsedResponseRecord
    ) -> list[ResponseData]:
        """Extract the text from a server response message."""
        ...


################################################################################
# Service Protocol
################################################################################


@runtime_checkable
class BaseServiceProtocol(Protocol):
    """Base protocol for all services."""


@runtime_checkable
class ProxyProtocol(Protocol):
    """Base protocol for all proxies."""

    async def start(self) -> None:
        """Start the proxy."""
        ...

    async def stop(self) -> None:
        """Stop the proxy."""
        ...

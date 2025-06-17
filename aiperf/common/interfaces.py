#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Generic, Protocol

from aiperf.common.config import EndPointConfig
from aiperf.common.models import (
    InferenceServerResponse,
    ProfileResultsMessage,
    RequestRecord,
)
from aiperf.common.types import ConfigT, InputT, OutputT, RequestT, ResponseT

################################################################################
# Converter Protocols
################################################################################


class InputConverterProtocol(Protocol, Generic[InputT, RequestT]):
    """Protocol for an input converter."""

    async def convert(self, input: InputT) -> RequestT:
        """Convert the input to the expected format."""
        ...


class OutputConverterProtocol(Protocol, Generic[OutputT, ResponseT]):
    """Protocol for an output converter."""

    async def convert(self, output: OutputT) -> ResponseT:
        """Convert the output to the expected format."""
        ...


################################################################################
# Inference Server Client Protocols
################################################################################


class InferenceClientProtocol(Protocol, Generic[ConfigT, RequestT, ResponseT]):
    """Protocol for an inference server client.

    This protocol defines the methods that must be implemented by any inference server client
    implementation that is compatible with the AIPerf framework.
    """

    def __init__(self, client_config: ConfigT) -> None:
        """Create a new inference server client based on the provided configuration."""
        ...

    @property
    def client_config(self) -> ConfigT:
        """Get the client configuration."""
        ...

    async def format_payload(
        self, endpoint: EndPointConfig, payload: RequestT
    ) -> RequestT:
        """Format the payload for the inference server.

        This method is used to format the payload for the inference server.

        Args:
            payload: The payload to format.

        Returns:
            The formatted payload.
        """
        ...

    async def send_request(
        self, endpoint: EndPointConfig, payload: RequestT, delayed: bool = False
    ) -> RequestRecord:
        """Send a request to the inference server.

        This method is used to send a request to the inference server.

        Args:
            endpoint: The endpoint to send the request to.
            payload: The payload to send to the inference server.
            delayed: Whether the request is delayed.
        Returns:
            The raw response from the inference server.
        """
        ...

    async def parse_response(self, response: ResponseT) -> InferenceServerResponse:
        """Parse the response from the inference server.

        This method is used to parse the response from the inference server.

        Args:
            response: The raw response from the inference server.

        Returns:
            The parsed response from the inference server.
        """
        ...

    async def cleanup(self) -> None:
        """Cleanup the client."""
        ...

    ################################################################################
    # Post Processor Protocol
    ################################################################################
    class PostProcessorProtocol(Protocol):
        """
        PostProcessorProtocol is a protocol that defines the API for post-processors.
        It requires an `process` method that takes a list of records and returns a result.
        """

        def process(self, records: dict) -> dict:
            """
            Execute the post-processing logic on the given records.

            :param records: The input data to be processed.
            :return: The processed data as a dictionary.
            """
            ...


################################################################################
# Data Exporter Protocol
################################################################################


class DataExporterProtocol(Protocol):
    """
    Protocol for data exporters.
    Any class implementing this protocol must provide an `export` method
    that takes a list of Record objects and handles exporting them appropriately.
    """

    def export(self, message: ProfileResultsMessage) -> None: ...

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Generic, Protocol, runtime_checkable

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.dataset_models import Turn
from aiperf.common.enums import EndpointType
from aiperf.common.factories import FactoryMixin
from aiperf.common.record_models import RequestRecord
from aiperf.common.types import InputT, OutputT, RequestT, ResponseT

# from aiperf.converters.base_converter import RequestConverterProtocol


################################################################################
# Inference Server Client Protocols
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


@runtime_checkable
class InferenceClientProtocol(Protocol, Generic[RequestT]):
    """Protocol for an inference server client.

    This protocol defines the methods that must be implemented by any inference server client
    implementation that is compatible with the AIPerf framework.
    """

    def __init__(self, model_endpoint: ModelEndpointInfo) -> None:
        """Create a new inference server client based on the provided configuration."""
        ...

    async def initialize(self) -> None:
        """Initialize the inference server client in an asynchronous context."""
        ...

    async def format_payload(
        self, model_endpoint: ModelEndpointInfo, turn: Turn
    ) -> RequestT:
        """Format the turn for the inference server."""
        ...

    async def send_request(
        self,
        model_endpoint: ModelEndpointInfo,
        payload: RequestT,
    ) -> RequestRecord:
        """Send a request to the inference server.

        This method is used to send a request to the inference server.

        Args:
            model_endpoint: The endpoint to send the request to.
            payload: The payload to send to the inference server.
        Returns:
            The raw response from the inference server.
        """
        ...

    async def close(self) -> None:
        """Close the client."""
        ...


class InferenceClientFactory(FactoryMixin[EndpointType, InferenceClientProtocol]):
    """Factory for registering and creating InferenceClientProtocol instances based on the specified endpoint type.
    see: :class:`FactoryMixin` for more details.
    """


class OutputConverterFactory(FactoryMixin[EndpointType, OutputConverterProtocol]):
    """Factory for registering and creating OutputConverterProtocol instances based on the specified output format.
    see: :class:`FactoryMixin` for more details.
    """


class RequestConverterFactory(FactoryMixin[EndpointType, "RequestConverterProtocol"]):
    """Factory for registering and creating RequestPayloadConverter instances based on the specified request payload type.
    see: :class:`FactoryMixin` for more details.
    """

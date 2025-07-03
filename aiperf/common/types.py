# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from aiperf.common.enums import Modality, ModelSelectionStrategy, RequestPayloadType

ConfigT = TypeVar("ConfigT", bound=Any, covariant=True)
RequestT = TypeVar("RequestT", bound=Any)
ResponseT = TypeVar("ResponseT", bound=Any, covariant=True)
RawResponseT = TypeVar("RawResponseT", bound=Any, contravariant=True)
InputT = TypeVar("InputT", bound=Any)
OutputT = TypeVar("OutputT", bound=Any)
RawRequestT = TypeVar("RawRequestT", bound=Any, contravariant=True)


class ModelInfo(BaseModel):
    """Information about a model."""

    name: str = Field(
        description="The name of the model. This is used to identify the model.",
    )
    version: str | None = Field(
        default=None,
        description="The version of the model.",
    )
    modality: Modality = Field(
        default=Modality.CUSTOM,
        description="The modality of the model. This is used to determine the type of request payload to use for the endpoint. If CUSTOM, the model is not supported.",
    )
    extra: dict[str, Any] | None = Field(
        default=None,
        description="Extra information to use for the model. This is used to store additional information about the model for future use.",
    )


class EndpointInfo(BaseModel):
    """Information about an endpoint."""

    request_payload_type: RequestPayloadType = Field(
        default=RequestPayloadType.OPENAI_CHAT_COMPLETIONS,
        description="The type of request payload to use for the endpoint.",
    )
    custom_endpoint: str | None = Field(
        default=None,
        description="Custom endpoint to use for the models. If None, the endpoint will be the same as the model's endpoint.",
    )
    extra: dict[str, Any] | BaseModel | None = Field(
        default=None,
        description="Extra information to send with the inference request.",
    )


class HttpEndpointInfo(EndpointInfo):
    """Information about an HTTP endpoint."""

    base_url: str | None = Field(
        default=None,
        description="URL to use for the endpoint. If None, the URL will be the same as the model's URL.",
    )
    custom_url_params: dict[str, Any] | None = Field(
        default=None,
        description="Custom URL parameters to use for the endpoint. If None, the URL parameters will be the same as the model's URL parameters.",
    )
    custom_headers: dict[str, Any] | None = Field(
        default=None,
        description="Custom URL headers to use for the endpoint. If None, the URL headers will be the same as the model's URL headers.",
    )
    api_key: str | None = Field(
        default=None,
        description="API key to use for the endpoint. If None, the API key will be the same as the model's API key.",
    )
    ssl_options: dict[str, Any] | None = Field(
        default=None,
        description="SSL options to use for the endpoint. If None, the SSL options will be the same as the model's SSL options.",
    )


class ModelEndpointInfo(BaseModel):
    """Information about a model endpoint."""

    models: list[ModelInfo] = Field(
        description="The models to use for the endpoint.",
    )
    endpoint: EndpointInfo = Field(
        description="The endpoint to use for the models.",
    )
    model_selection_strategy: ModelSelectionStrategy = Field(
        description="The strategy to use for selecting the model to use for the endpoint.",
    )

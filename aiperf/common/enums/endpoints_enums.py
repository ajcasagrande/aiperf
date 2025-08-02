# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from pydantic import BaseModel, Field
from typing_extensions import Self

from aiperf.common.enums.base_enums import CaseInsensitiveStrEnum


class EndpointInfo(BaseModel):
    """Pydantic model for endpoint-specific information."""

    tag: str = Field(..., description="The string value for the endpoint type.")
    supports_streaming: bool = Field(
        ..., description="True if the endpoint supports streaming, False otherwise."
    )
    produces_tokens: bool = Field(
        ..., description="True if the endpoint produces tokens, False otherwise."
    )
    endpoint_path: str | None = Field(
        None,
        description="The default URL path for the endpoint. If None, the endpoint does not have a specific path.",
    )
    metrics_title: str | None = Field(
        None,
        description="The title string for the endpoint type. If None, the endpoint does not have a specific title.",
    )


class EndpointType(CaseInsensitiveStrEnum):
    """Endpoint types.

    These determine the format of request payload to send to the model.

    Similar to `endpoint_type_map` and `OutputFormat` from `GenAI-Perf`.
    """

    OPENAI_CHAT_COMPLETIONS = EndpointInfo(
        tag="chat",
        supports_streaming=True,
        produces_tokens=True,
        endpoint_path="/v1/chat/completions",
        metrics_title="LLM Metrics",
    )
    OPENAI_COMPLETIONS = EndpointInfo(
        tag="completions",
        supports_streaming=True,
        produces_tokens=True,
        endpoint_path="/v1/completions",
        metrics_title="LLM Metrics",
    )
    OPENAI_EMBEDDINGS = EndpointInfo(
        tag="embeddings",
        supports_streaming=False,
        produces_tokens=False,
        endpoint_path="/v1/embeddings",
        metrics_title="Embeddings Metrics",
    )
    OPENAI_RESPONSES = EndpointInfo(
        tag="responses",
        supports_streaming=True,
        produces_tokens=True,
        endpoint_path="/v1/responses",
        metrics_title="LLM Metrics",
    )

    def __new__(cls, endpoint_info: EndpointInfo) -> Self:
        obj = str.__new__(cls, endpoint_info.tag)
        # Ensure string value is set for comparison
        obj._value_ = endpoint_info.tag
        # Store the Pydantic model as an attribute
        obj.info: EndpointInfo = endpoint_info  # type: ignore
        return obj

    @property
    def info(self) -> EndpointInfo:
        """Get the endpoint info for the endpoint type."""
        return self.info

    @property
    def supports_streaming(self) -> bool:
        """Return True if the endpoint supports streaming. This is used for validation of user input."""  # TODO:: add this validation to the user config
        return self.info.supports_streaming

    @property
    def produces_tokens(self) -> bool:
        """Return True if the endpoint produces tokens. This is used to determine what metrics are applicable to the endpoint."""
        return self.info.produces_tokens

    @property
    def endpoint_path(self) -> str | None:
        """Get the default endpoint path for the endpoint type."""
        return self.info.endpoint_path

    @property
    def metrics_title(self) -> str:
        """Get the title string for the endpoint type."""
        return self.info.metrics_title or "LLM Metrics"

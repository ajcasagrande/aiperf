#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
"""Pydantic models for messages used in inter-service communication."""

import time

from pydantic import BaseModel, Field

from aiperf.core.message.payload import PayloadProtocol


class BaseMessage(BaseModel):
    """Base message model with shared fields for all messages.
    The payload can be any of the payload types defined by the payloads.py module.

    The message type is determined by the discriminator field `message_type`. This is
    used by the Pydantic `discriminator` argument to determine the type of the
    payload automatically when the message is deserialized from a JSON string.

    To serialize a message to a JSON string, use the `model_dump_json` method.
    To deserialize a message from a JSON string, use the `model_validate_json`
    method.

    Example:
    ```python
    >>> message = BaseMessage(
    ...     service_id="service_1",
    ...     request_id="request_1",
    ...     payload=DataPayload(data="Hello, world!"),
    ... )
    >>> json_string = message.model_dump_json()
    >>> print(json_string)
    {"payload": {"data": "Hello, world!"}, "service_id": "service_1", "request_id": "request_1"}
    >>> deserialized_message = BaseMessage.model_validate_json(json_string)
    >>> print(deserialized_message)
    BaseMessage(
        payload=DataPayload(data="Hello, world!"),
        service_id="service_1",
        request_id="request_1",
        timestamp=1716278400000000000,
    )
    >>> print(deserialized_message.payload.data)
    Hello, world!
    ```
    """

    service_id: str | None = Field(
        default=None,
        description="ID of the service sending the response",
    )
    timestamp: int = Field(
        default_factory=time.time_ns,
        description="Time when the response was created",
    )
    request_id: str | None = Field(
        default=None,
        description="ID of the request",
    )
    payload: PayloadProtocol = Field(
        ...,
        discriminator="message_type",
        description="Payload of the response",
    )

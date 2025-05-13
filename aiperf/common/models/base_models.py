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
"""Base Pydantic models used across the application."""

from typing import Any, Dict, Optional, TypeVar

from pydantic import BaseModel, Field


class BasePayload(BaseModel):
    """Base model for all payload data."""


PayloadT = TypeVar("PayloadT", bound=BasePayload)


class RequestResponseBasePayload(BasePayload):
    """Base payload for request-response patterns."""

    transaction_id: Optional[str] = Field(
        default=None,
        description="Optional transaction ID for tracking request-response flows",
    )


class DataPayload(BasePayload):
    """Base model for data payloads with metadata."""

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata for the payload",
    )

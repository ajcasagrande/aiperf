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
"""Pydantic models for push-pull patterns used in communication."""

import time
from typing import Any, Optional

from pydantic import BaseModel, Field

from aiperf.common.models.base_models import BasePayload


class PushPullData(BaseModel):
    """Base model for push data."""

    source: str = Field(
        ...,
        description="ID of the source sending the data",
    )
    topic: str = Field(
        ...,
        description="Topic to which the data is being sent",
    )
    timestamp: float = Field(
        default_factory=time.time,
        description="Time when the data was created",
    )
    data: Any = Field(
        ...,
        description="Data payload as a dictionary (for backward compatibility)",
    )
    payload: Optional[BasePayload] = Field(
        default=None,
        description="Structured data payload (Pydantic model)",
    )

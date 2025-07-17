# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import time
from typing import Any

from pydantic import Field

from aiperf.common.enums import (
    ServiceState,
    ServiceType,
)
from aiperf.common.models._base import AIPerfBaseModel
from aiperf.common.models._error import ErrorDetails
from aiperf.common.models._health import ProcessHealth


class ServiceRegistrationInfo(AIPerfBaseModel):
    """Base model for tracking service registration information."""

    service_id: str = Field(..., description="The ID of the service")
    service_type: ServiceType = Field(..., description="The type of service")
    address: str | None = Field(
        default=None, description="The address of the service (if known)"
    )
    first_seen: int | None = Field(
        default_factory=time.time_ns, description="The first time the service was seen"
    )
    last_seen: int | None = Field(
        default_factory=time.time_ns,
        description="The most recent time the service was seen",
    )
    state: ServiceState = Field(
        default=ServiceState.UNKNOWN,
        description="The current state of the service (if known)",
    )
    process_health: ProcessHealth | None = Field(
        default=None, description="The current process health of the service (if known)"
    )
    errors: list[ErrorDetails] = Field(
        default_factory=list, description="The errors the service has encountered"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Any miscellaneous metadata about the service"
    )

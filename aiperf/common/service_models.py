# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import time

from pydantic import Field

from aiperf.common.enums import (
    ServiceRegistrationStatus,
    ServiceState,
    ServiceType,
)
from aiperf.common.health_models import ProcessHealth
from aiperf.common.pydantic_utils import AIPerfBaseModel
from aiperf.common.record_models import ErrorDetails


class ServiceRegistrationInfo(AIPerfBaseModel):
    """Base model for tracking service registration information."""

    service_id: str = Field(..., description="The ID of the service")
    service_type: ServiceType = Field(..., description="The type of service")
    address: str = Field(..., description="The address of the service (if known)")
    registration_status: ServiceRegistrationStatus = Field(
        ..., description="The registration status of the service"
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

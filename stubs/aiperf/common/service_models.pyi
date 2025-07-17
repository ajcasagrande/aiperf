#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Any

from aiperf.common.enums import ServiceState as ServiceState
from aiperf.common.enums import ServiceType as ServiceType
from aiperf.common.health_models import ProcessHealth as ProcessHealth
from aiperf.common.pydantic_utils import AIPerfBaseModel as AIPerfBaseModel
from aiperf.common.record_models import ErrorDetails as ErrorDetails

class ServiceRegistrationInfo(AIPerfBaseModel):
    service_id: str
    service_type: ServiceType
    address: str | None
    first_seen: int | None
    last_seen: int | None
    state: ServiceState
    process_health: ProcessHealth | None
    errors: list[ErrorDetails]
    metadata: dict[str, Any]

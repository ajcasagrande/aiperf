#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Annotated

from _typeshed import Incomplete
from pydantic import BeforeValidator as BeforeValidator
from pydantic import Field as Field
from pydantic_settings import BaseSettings
from typing_extensions import Self

from aiperf.common.config._base import ADD_TO_TEMPLATE as ADD_TO_TEMPLATE
from aiperf.common.config._defaults import ServiceDefaults as ServiceDefaults
from aiperf.common.config._validators import parse_service_types as parse_service_types
from aiperf.common.config._validators import parse_ui_type as parse_ui_type
from aiperf.common.config._workers import WorkersConfig as WorkersConfig
from aiperf.common.config._zmq import (
    BaseZMQCommunicationConfig as BaseZMQCommunicationConfig,
)
from aiperf.common.config._zmq import ZMQIPCConfig as ZMQIPCConfig
from aiperf.common.config._zmq import ZMQTCPConfig as ZMQTCPConfig
from aiperf.common.enums import AIPerfLogLevel as AIPerfLogLevel
from aiperf.common.enums import AIPerfUIType as AIPerfUIType
from aiperf.common.enums import CommunicationBackend as CommunicationBackend
from aiperf.common.enums import ServiceRunType as ServiceRunType
from aiperf.common.enums import ServiceType as ServiceType

class ServiceConfig(BaseSettings):
    model_config: Incomplete
    log_level: Incomplete
    def validate_log_level_from_verbose_flags(self) -> Self: ...
    comm_config: Incomplete
    def validate_comm_config(self) -> Self: ...
    ui_type: Incomplete
    def validate_ui_type(self) -> Self: ...
    service_run_type: Annotated[ServiceRunType, None, None]
    comm_backend: Annotated[CommunicationBackend, None, None]
    heartbeat_timeout: Annotated[float, None, None]
    registration_timeout: Annotated[float, None, None]
    command_timeout: Annotated[float, None, None]
    heartbeat_interval_seconds: Annotated[float, None, None]
    workers: Annotated[WorkersConfig, None]
    verbose: Annotated[bool, None, None]
    extra_verbose: Annotated[bool, None, None]
    basic_ui: Annotated[bool, None, None]
    disable_ui: Annotated[bool, None, None]
    enable_uvloop: Annotated[bool, None, None]
    result_parser_service_count: Annotated[int, None, None]
    enable_yappi: Annotated[bool, None, None]
    debug_services: Annotated[set[ServiceType] | None, None, None, None]
    trace_services: Annotated[set[ServiceType] | None, None, None, None]

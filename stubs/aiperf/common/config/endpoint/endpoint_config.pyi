#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Annotated

from pydantic import BeforeValidator as BeforeValidator
from pydantic import Field as Field

from aiperf.common.config._base import BaseConfig as BaseConfig
from aiperf.common.config._defaults import EndPointDefaults as EndPointDefaults
from aiperf.common.config._validators import (
    parse_str_or_list as parse_str_or_list,
)
from aiperf.common.enums import EndpointType as EndpointType
from aiperf.common.enums import ModelSelectionStrategy as ModelSelectionStrategy

class EndPointConfig(BaseConfig):
    model_selection_strategy: Annotated[ModelSelectionStrategy, None, None]
    custom_endpoint: Annotated[str | None, None, None]
    type: Annotated[EndpointType, None, None]
    streaming: Annotated[bool, None, None]
    server_metrics_urls: Annotated[list[str], None, None, None]
    url: Annotated[str, None, None]
    grpc_method: Annotated[str, None, None]
    timeout_seconds: Annotated[float, None, None]
    api_key: Annotated[str | None, None, None]

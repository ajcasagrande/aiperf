#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Annotated

from _typeshed import Incomplete
from pydantic import Field as Field

from aiperf.common.config import ServiceConfig as ServiceConfig
from aiperf.common.config import UserConfig as UserConfig
from aiperf.common.config.config_defaults import CLIDefaults as CLIDefaults

app: Incomplete

def profile(
    user_config: UserConfig, service_config: ServiceConfig | None = None
) -> None: ...
def analyze(
    user_config: UserConfig, service_config: ServiceConfig | None = None
) -> None: ...
def create_template(template_filename: Annotated[str, None, None] = ...) -> None: ...
def validate_config(
    user_config: UserConfig | None = None, service_config: ServiceConfig | None = None
) -> None: ...

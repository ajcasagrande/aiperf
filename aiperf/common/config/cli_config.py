# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Annotated

import cyclopts
from pydantic import BaseModel, Field

from aiperf.common.config.base_config import ADD_TO_TEMPLATE
from aiperf.common.config.config_defaults import CLIDefaults


class CLIConfig(BaseModel):
    """Additional CLI only configuration options."""

    verbose: Annotated[
        bool,
        Field(
            description="Equivalent to --log-level DEBUG. Enables more verbose logging output, but lacks some raw message logging.",
            json_schema_extra={ADD_TO_TEMPLATE: False},
        ),
        cyclopts.Parameter(
            name=("--verbose", "-v"),
        ),
    ] = CLIDefaults.VERBOSE

    extra_verbose: Annotated[
        bool,
        Field(
            description="Equivalent to --log-level TRACE. Enables the most verbose logging output possible.",
            json_schema_extra={ADD_TO_TEMPLATE: False},
        ),
        cyclopts.Parameter(
            name=("--extra-verbose", "-vv"),
        ),
    ] = CLIDefaults.EXTRA_VERBOSE

    template_filename: Annotated[
        str,
        Field(
            description="Path to the template file.",
            json_schema_extra={ADD_TO_TEMPLATE: False},
        ),
        cyclopts.Parameter(
            name=("--template-filename", "-t"),
        ),
    ] = CLIDefaults.TEMPLATE_FILENAME

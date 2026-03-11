# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Environment variable inspection CLI command.

aiperf env                           # Show env vars set to non-default values
aiperf env --all                     # Show all env vars with current values
aiperf env --describe                # Include descriptions in output
aiperf env --defaults                # Reference table: all vars, defaults, constraints, descriptions
aiperf env http                      # Filter to a specific subsystem
aiperf env http --all                # All vars in that subsystem
"""

from __future__ import annotations

from typing import Annotated

from cyclopts import App, Parameter

app = App(name="env")


@app.default
def env(
    subsystem: Annotated[
        str | None, Parameter(help="Subsystem to filter (e.g. http, worker, zmq)")
    ] = None,
    *,
    all_vars: Annotated[
        bool,
        Parameter(
            name=["--all", "-a"], help="Show all env vars, not just overridden ones"
        ),
    ] = False,
    describe: Annotated[
        bool,
        Parameter(name=["--describe", "-d"], help="Include field descriptions"),
    ] = False,
    defaults: Annotated[
        bool,
        Parameter(
            name=["--defaults"],
            help="Show reference table with defaults and constraints",
        ),
    ] = False,
) -> None:
    """Inspect AIPerf environment variables: aiperf env [subsystem] [--all] [--describe] [--defaults]"""
    from aiperf.common.env_cli import show_defaults, show_env_vars

    if defaults or (all_vars and describe):
        show_defaults(subsystem=subsystem)
    else:
        show_env_vars(subsystem=subsystem, show_all=all_vars, describe=describe)

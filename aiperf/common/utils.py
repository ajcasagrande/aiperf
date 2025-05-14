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
import logging

from rich.console import Console
from rich.logging import RichHandler

# Create a central console object for rich logging
_console = Console()


def get_logger(name: str) -> logging.Logger:
    """Get a logger configured with rich for colored output.

    Args:
        name: The name for the logger

    Returns:
        A configured logger instance
    """
    logger = logging.getLogger(name)

    # Only configure if it hasn't been configured yet
    if not logger.handlers:
        handler = RichHandler(
            rich_tracebacks=True,
            show_path=True,
            console=_console,
            tracebacks_show_locals=True,
        )
        logger.addHandler(handler)

    return logger

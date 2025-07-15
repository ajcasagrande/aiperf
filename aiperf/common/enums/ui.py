# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums.base import CaseInsensitiveStrEnum


class AIPerfUIType(CaseInsensitiveStrEnum):
    """The type of UI to use."""

    RICH = "rich"
    """Rich-based UI Dashboard. Requires the rich package to be installed.
    Clean, simple, and easy to use.
    """

    TEXTUAL = "textual"
    """Textual-based UI Dashboard. Requires the textual package to be installed.
    Full feature terminal UI with scrolling and mouse support.
    """

    TQDM = "tqdm"
    """No dashboard, just simple progress bars using tqdm.
    Requires the tqdm package to be installed."""

    LOGGING = "logging"
    """Logs progress to the console as log messages. This can be considered a fallback
    for when no other UI is available.
    """

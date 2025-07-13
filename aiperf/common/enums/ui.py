# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums.base import CaseInsensitiveStrEnum


class AIPerfUIType(CaseInsensitiveStrEnum):
    """The type of UI to use."""

    RICH = "rich"
    TEXTUAL = "textual"
    TQDM = "tqdm"
    LOGGING = "logging"

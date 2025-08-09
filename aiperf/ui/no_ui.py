# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import AIPerfUIType
from aiperf.common.factories import AIPerfUIFactory
from aiperf.common.mixins.aiperf_base_ui_mixin import AIPerfBaseUIMixin


@AIPerfUIFactory.register(AIPerfUIType.NONE)
class NoUI(AIPerfBaseUIMixin):
    """A UI that does nothing."""

#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from abc import ABC, abstractmethod

from aiperf.common.mixins import AIPerfLifecycleMixin


class BasePlugin(AIPerfLifecycleMixin, ABC):
    """Base class for all plugins."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def on_start(self):
        pass

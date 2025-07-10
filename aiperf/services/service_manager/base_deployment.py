# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from abc import ABC, abstractmethod

from aiperf.common.messages import BaseServiceMessage


class BaseServiceDeployment(ABC):
    """Base class for managing services in a deployment."""

    @abstractmethod
    async def on_message(self, message: BaseServiceMessage) -> None:
        """Handle a message from a service."""
        pass

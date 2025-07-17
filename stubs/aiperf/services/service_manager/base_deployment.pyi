#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import abc
from abc import ABC, abstractmethod

from aiperf.common.messages import BaseServiceMessage as BaseServiceMessage

class BaseServiceDeployment(ABC, metaclass=abc.ABCMeta):
    @abstractmethod
    async def on_message(self, message: BaseServiceMessage) -> None: ...

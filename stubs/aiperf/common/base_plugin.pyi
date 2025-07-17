#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import abc
from abc import ABC, abstractmethod

from _typeshed import Incomplete

from aiperf.common.mixins import AIPerfLifecycleMixin as AIPerfLifecycleMixin

class BasePlugin(AIPerfLifecycleMixin, ABC, metaclass=abc.ABCMeta):
    name: Incomplete
    def __init__(self, name: str) -> None: ...
    @abstractmethod
    def on_start(self): ...

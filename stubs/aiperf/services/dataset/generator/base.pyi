#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import abc
from abc import ABC, abstractmethod

from _typeshed import Incomplete

class BaseGenerator(ABC, metaclass=abc.ABCMeta):
    logger: Incomplete
    def __init__(self) -> None: ...
    @abstractmethod
    def generate(self, *args, **kwargs) -> str: ...

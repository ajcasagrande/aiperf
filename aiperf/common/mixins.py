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
import uuid
from typing import Any

from aiperf.common.interfaces import (
    SupportsId,
    SupportsLogging,
    SupportsZMQConfig,
)
from aiperf.common.logging import TraceLogger
from aiperf.common.models.comms import ZMQCommunicationConfig


class LoggingMixin(SupportsLogging):
    """
    Mixin that provides logging capabilities conforming to SupportsLogging protocol.

    The logger is available immediately when a class inherits from this mixin,
    even in __init__ methods.
    """

    _logger: logging.Logger

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Set up class-specific logger when subclassed."""
        super().__init_subclass__(**kwargs)

        logger_name = f"{cls.__module__}.{cls.__qualname__}"
        cls._logger = logging.getLogger(logger_name)

    @property
    def logger(self) -> logging.Logger:
        """Get the logger for this class."""
        return self._logger


class TraceLoggingMixin:
    """Enhanced logging mixin with TRACE level support."""

    _logger: TraceLogger

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        logger_name = f"{cls.__module__}.{cls.__qualname__}"
        cls._logger = TraceLogger(logger_name)

    @property
    def logger(self) -> TraceLogger:
        return self._logger


class ZMQConfigMixin(SupportsZMQConfig):
    """Mixin for classes that support ZMQ configuration."""

    def __init__(self, zmq_config: ZMQCommunicationConfig, *args, **kwargs):
        self._zmq_config = zmq_config
        super().__init__(*args, **kwargs)

    @property
    def zmq_config(self) -> ZMQCommunicationConfig:
        """Get the ZMQ configuration for the class."""
        return self._zmq_config


class SupportsIdMixin(SupportsId):
    """Mixin for classes that support getting an ID."""

    def __init__(self, id: str | None = None, *args, **kwargs) -> None:
        self._id = id or uuid.uuid4().hex
        super().__init__(*args, **kwargs)

    @property
    def id(self) -> str:
        """Get the ID of the class."""
        return self._id

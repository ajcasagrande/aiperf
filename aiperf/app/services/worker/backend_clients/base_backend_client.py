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


from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from aiperf.common.interfaces.backend_client_interface import BackendClientInterface
from aiperf.common.models.backend_clients.backend_client_models import (
    BackendClientConfig,
)

ConfigT = TypeVar("ConfigT", bound=BaseModel)
RequestT = TypeVar("RequestT", bound=Any)
ResponseT = TypeVar("ResponseT", bound=Any)


class BaseBackendClient(
    BackendClientInterface, ABC, Generic[ConfigT, RequestT, ResponseT]
):
    """Base class for all backend clients.

    This class is responsible for formatting payloads, sending requests, and parsing responses for all backend clients.
    """

    def __init__(self, client_config: BackendClientConfig[ConfigT]):
        self.client_config: BackendClientConfig[ConfigT] = client_config

    @abstractmethod
    def format_payload(self, payload: Any) -> RequestT:
        raise NotImplementedError("BaseBackendClient should not be used directly")

    @abstractmethod
    def send_request(self, endpoint: str, payload: RequestT) -> Any:
        raise NotImplementedError("BaseBackendClient should not be used directly")

    @abstractmethod
    def parse_response(self, response: Any) -> ResponseT:
        raise NotImplementedError("BaseBackendClient should not be used directly")

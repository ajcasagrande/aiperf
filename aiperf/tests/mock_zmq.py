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
# Create mock modules to prevent actual ZMQ imports before any real imports happen
from unittest.mock import MagicMock


class MockZMQSocket(MagicMock):
    """Mock ZMQ socket to prevent actual network operations."""

    def __init__(self, *args, **kwargs):
        pass

    def bind(self, *args, **kwargs):
        pass

    def connect(self, *args, **kwargs):
        pass

    def send(self, *args, **kwargs):
        pass

    def send_multipart(self, *args, **kwargs):
        pass

    def recv(self, *args, **kwargs):
        return b""

    def recv_multipart(self, *args, **kwargs):
        return [b"", b""]

    def close(self, *args, **kwargs):
        pass

    def setsockopt(self, *args, **kwargs):
        pass


class MockZMQContext(MagicMock):
    """Mock ZMQ context to prevent actual context creation."""

    def __init__(self, *args, **kwargs):
        pass

    def socket(self, *args, **kwargs):
        return MockZMQSocket()

    def term(self, *args, **kwargs):
        pass

#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.clients.http.base import (
    BaseHTTPClient,
    BaseHTTPClientConfig,
)


class HTTPXClient(BaseHTTPClient):
    def __init__(self, config: BaseHTTPClientConfig):
        self.config = config

#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.factories import FactoryMixin


class BackendClientFactory(FactoryMixin["BackendClientType", "BackendClientProtocol"]):
    """Factory for registering and creating BackendClientProtocol instances based on the specified backend client type.

    Example:
    ```python
        # Register a new backend client
        @BackendClientFactory.register(BackendClientType.OPENAI)
        class OpenAIBackendClient:
            pass  # Implement the BackendClientProtocol

        backend_client = BackendClientFactory.create_instance(
            BackendClientType.OPENAI,
            config=OpenAIBackendClientConfig(api_key="sk-1234567890"),
        )
        backend_client.send_request(...)
    ```
    """

#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
This package contains the backend clients for the AIPerf framework.

Backend clients are responsible for formatting payloads, sending requests, and parsing responses for communicating with the system under test.

They are registered with the :class:`aiperf.common.factories.BackendClientFactory`, which is responsible for creating backend client instances.
"""

from aiperf.backend.openai_client_aiohttp import OpenAIBackendClientAioHttp

__all__ = [
    "OpenAIBackendClientAioHttp",
]

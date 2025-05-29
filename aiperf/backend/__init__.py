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
"""
This package contains the backend clients for the AIPerf framework.

Backend clients are responsible for formatting payloads, sending requests, and parsing responses for communicating with the system under test.

They are registered with the :class:`aiperf.common.factories.BackendClientFactory`, which is responsible for creating backend client instances.
"""

from aiperf.backend.openai_client import OpenAIBackendClient

__all__ = ["OpenAIBackendClient"]

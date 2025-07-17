#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.enums.base import CaseInsensitiveStrEnum as CaseInsensitiveStrEnum

class EndpointType(CaseInsensitiveStrEnum):
    OPENAI_CHAT_COMPLETIONS = "chat"
    OPENAI_COMPLETIONS = "completions"
    OPENAI_RESPONSES = "responses"
    def endpoint_path(self) -> str | None: ...
    def response_payload_type(self) -> ResponsePayloadType: ...

class ResponsePayloadType(CaseInsensitiveStrEnum):
    OPENAI_CHAT_COMPLETIONS = "openai_chat_completions"
    OPENAI_COMPLETIONS = "openai_completions"
    OPENAI_RESPONSES = "openai_responses"
    @classmethod
    def from_endpoint_type(cls, endpoint_type: EndpointType) -> ResponsePayloadType: ...

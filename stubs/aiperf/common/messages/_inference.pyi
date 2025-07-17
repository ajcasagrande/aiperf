#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Literal

from pydantic import SerializeAsAny as SerializeAsAny

from aiperf.common.enums import MessageType as MessageType
from aiperf.common.messages._base import BaseServiceMessage as BaseServiceMessage
from aiperf.common.models import ParsedResponseRecord as ParsedResponseRecord
from aiperf.common.models import RequestRecord as RequestRecord

class InferenceResultsMessage(BaseServiceMessage):
    message_type: Literal[MessageType.INFERENCE_RESULTS]
    record: SerializeAsAny[RequestRecord]

class ParsedInferenceResultsMessage(BaseServiceMessage):
    message_type: Literal[MessageType.PARSED_INFERENCE_RESULTS]
    record: SerializeAsAny[ParsedResponseRecord]

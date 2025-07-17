#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Literal

from aiperf.common.enums import MessageType as MessageType
from aiperf.common.messages.base import BaseServiceMessage as BaseServiceMessage
from aiperf.common.messages.base import Message as Message
from aiperf.common.record_models import ErrorDetails as ErrorDetails

class ErrorMessage(Message):
    message_type: Literal[MessageType.ERROR]
    error: ErrorDetails

class BaseServiceErrorMessage(BaseServiceMessage):
    message_type: Literal[MessageType.SERVICE_ERROR]
    error: ErrorDetails

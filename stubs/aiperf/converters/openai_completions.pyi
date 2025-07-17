#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Any

from aiperf.clients.converters.base_converter import (
    BaseRequestConverter as BaseRequestConverter,
)
from aiperf.common.config import OutputTokenDefaults as OutputTokenDefaults
from aiperf.common.enums import EndpointType as EndpointType
from aiperf.common.factories import RequestConverterFactory as RequestConverterFactory
from aiperf.common.models import GenericDataset as GenericDataset

class OpenAICompletionsRequestConverter(BaseRequestConverter):
    def convert(self, generic_dataset: GenericDataset) -> dict[Any, Any]: ...

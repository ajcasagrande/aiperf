#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

# TODO: This file needs cleanup and refactoring after bringing in from GAP

from typing import Any

from aiperf.clients.converters.base_converter import BaseRequestConverter
from aiperf.common.config import OutputTokenDefaults
from aiperf.common.enums import RequestPayloadType
from aiperf.common.factories import RequestConverterFactory
from aiperf.common.models.data_models import GenericDataset


@RequestConverterFactory.register(RequestPayloadType.OPENAI_COMPLETIONS)
class OpenAICompletionsRequestConverter(BaseRequestConverter):
    def convert(
        self,
        generic_dataset: GenericDataset,
    ) -> dict[Any, Any]:
        request_body: dict[str, Any] = {"data": []}

        for file_data in generic_dataset.files_data.values():
            for index, row in enumerate(file_data.rows):
                model_name = self._select_model_name(index, row)
                prompt = row.texts

                payload = {
                    "model": model_name,
                    "prompt": prompt,
                }
                request_body["data"].append(self._finalize_payload(payload, row))

        return request_body

    def _add_request_params(self, payload: dict, optional_data: dict[Any, Any]) -> None:
        if self.config.endpoint.streaming:
            payload["stream"] = True

        max_tokens = self._get_max_tokens(optional_data)
        if max_tokens != OutputTokenDefaults.MEAN:
            payload["max_tokens"] = max_tokens

        if self.config.input.extra:
            for key, value in self.config.input.extra.items():
                payload[key] = value

#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

from typing import Any

from aiperf.clients.converters.base_converter import BaseRequestConverter
from aiperf.common.config import InputDefaults, OutputTokenDefaults
from aiperf.common.enums import RequestPayloadType
from aiperf.common.exceptions import AIPerfError
from aiperf.common.factories import RequestConverterFactory
from aiperf.common.models.data_models import DataRow, GenericDataset

# TODO: This file needs heavy cleanup and refactoring after bringing in from GAP


@RequestConverterFactory.register(RequestPayloadType.OPENAI_CHAT_COMPLETIONS)
@RequestConverterFactory.register(RequestPayloadType.OPENAI_MULTIMODAL)
class OpenAIChatCompletionsRequestConverter(BaseRequestConverter):
    def check_config(self) -> None:
        if (
            self.config.endpoint.output_format
            == RequestPayloadType.OPENAI_CHAT_COMPLETIONS
            or self.config.endpoint.output_format
            == RequestPayloadType.OPENAI_MULTIMODAL
        ):
            if self.config.input.batch_size != InputDefaults.BATCH_SIZE:
                raise AIPerfError(
                    f"The --batch-size-text flag is not supported for {self.config.endpoint.output_format}."
                )
            if self.config.input.image.batch_size != InputDefaults.BATCH_SIZE:
                raise AIPerfError(
                    f"The --batch-size-image flag is not supported for {self.config.endpoint.output_format}."
                )

    def convert(
        self,
        generic_dataset: GenericDataset,
    ) -> dict[Any, Any]:
        request_body: dict[str, Any] = {"data": []}

        for file_data in generic_dataset.files_data.values():
            for index, row in enumerate(file_data.rows):
                payload = self._create_payload(index, row)
                request_body["data"].append(self._finalize_payload(payload, row))

        return request_body

    def _create_payload(self, index: int, row: DataRow) -> dict[Any, Any]:
        model_name = self._select_model_name(index, row)
        content = self._retrieve_content(row)

        payload = {
            "model": model_name,
            "messages": [
                {
                    # TODO: Allow for different roles
                    "role": "user",
                    "content": content,
                }
            ],
        }

        return payload

    def _retrieve_content(self, row: DataRow) -> str | list[dict[Any, Any]]:
        content: str | list[dict[Any, Any]] = ""
        if (
            self.config.endpoint.output_format
            == RequestPayloadType.OPENAI_CHAT_COMPLETIONS
        ):
            content = row.texts[0]
        elif self.config.endpoint.output_format == RequestPayloadType.OPENAI_MULTIMODAL:
            content = self._add_multi_modal_content(row)
        else:
            raise AIPerfError(
                f"Output format {self.config.endpoint.output_format} is not supported"
            )
        return content

    def _add_multi_modal_content(self, entry: DataRow) -> list[dict[Any, Any]]:
        content: list[dict[Any, Any]] = []
        for text in entry.texts:
            content.append(
                {
                    "type": "text",
                    "text": text,
                }
            )
        for image in entry.images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image,
                    },
                }
            )
        for audio in entry.audios:
            format, b64_audio = audio.split(",")
            content.append(
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": b64_audio,
                        "format": format,
                    },
                }
            )
        return content

    def _add_request_params(self, payload: dict, optional_data: dict[Any, Any]) -> None:
        if self.config.endpoint.streaming:
            payload["stream"] = True
        max_tokens = self._get_max_tokens(optional_data)
        if max_tokens != OutputTokenDefaults.MEAN:
            payload["max_tokens"] = max_tokens
        if self.config.input.extra:
            for key, value in self.config.input.extra.items():
                payload[key] = value

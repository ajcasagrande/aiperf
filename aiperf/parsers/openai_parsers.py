# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
from typing import Any

from aiperf.common.models import RequestRecord, ResponseData, SSEMessage, TextResponse
from aiperf.common.models.record_models import InferenceServerResponse
from aiperf.common.tokenizer import Tokenizer
from aiperf.common.utils import load_json_str

logger = logging.getLogger(__name__)


# TODO: Factory support for different supported parsers/extractors
class OpenAIResponseExtractor:
    """Extractor for OpenAI responses."""

    async def _parse_text_response(self, response: TextResponse) -> ResponseData | None:
        """Parse a TextResponse into a ResponseData object."""
        raw = response.text
        parsed, metadata = self._parse_text(raw)
        if parsed is None:
            return None

        return ResponseData(
            perf_ns=response.perf_ns,
            raw_text=[raw],
            parsed_text=parsed,
            metadata=metadata or {},
        )

    async def _parse_sse_response(self, response: SSEMessage) -> ResponseData | None:
        """Parse a SSEMessage into a ResponseData object."""
        raw = response.extract_data_content()
        parsed, metadata = self._parse_sse(raw)
        if parsed is None:
            return None

        return ResponseData(
            perf_ns=response.perf_ns,
            raw_text=raw,
            parsed_text=parsed,
            metadata=metadata or {},
        )

    async def _parse_response(
        self, response: InferenceServerResponse
    ) -> ResponseData | None:
        """Parse a response into a ResponseData object."""
        if isinstance(response, TextResponse):
            return await self._parse_text_response(response)
        elif isinstance(response, SSEMessage):
            return await self._parse_sse_response(response)

    async def extract_response_data(
        self, record: RequestRecord, tokenizer: Tokenizer | None
    ) -> list[ResponseData]:
        """Extract the text from a server response message."""
        results = []
        for response in record.responses:
            response_data = await self._parse_response(response)
            if response_data is not None:
                if tokenizer is not None:
                    response_data.token_count = sum(
                        len(tokenizer.encode(text))
                        for text in response_data.parsed_text
                        if text is not None
                    )
                results.append(response_data)
        return results

    def _parse_text(
        self, raw_text: str
    ) -> tuple[list[str] | None, dict[str, Any] | None]:
        """Parse the text of the response."""
        if raw_text in ("", None, "[DONE]"):
            return None, {}

        js = load_json_str(raw_text)
        if "choices" not in js:
            raise ValueError(f"Invalid OpenAI response: {js}")

        # TODO: how to support multiple choices?

        metadata = {
            "id": js["id"],
            "model": js["model"],
            "object": js["object"],
        }
        if "usage" in js:
            metadata["usage"] = js["usage"]

        # TODO: Parse based on the object type

        choice = js["choices"][0]
        if "text" in choice:
            return [choice["text"]], metadata
        elif "delta" in choice:
            if "content" in choice["delta"] and choice["delta"]["content"] not in (
                None,
                "",
            ):
                # logger.debug("Parsing delta: %s", choice["delta"])
                return [choice["delta"]["content"]], metadata

        elif "message" in choice:
            if choice["message"]["role"] == "assistant" and choice["message"][
                "content"
            ] not in (None, ""):
                metadata["role"] = "assistant"
                return [choice["message"]["content"]], metadata

        else:
            raise ValueError(f"Invalid OpenAI response: {js}")
        return None, metadata

    def _parse_sse(
        self, raw_sse: list[str]
    ) -> tuple[list[str] | None, dict[str, Any] | None]:
        """Parse the SSE of the response."""
        result = []
        all_metadata = {}
        for sse in raw_sse:
            parsed, metadata = self._parse_text(sse)
            if parsed is None:
                continue
            result.extend(parsed)

            if metadata is None:
                continue

            # TODO: right now we are merging metadata, not sure if correct approach
            for k, v in metadata.items():
                if k not in all_metadata:
                    all_metadata[k] = v
                else:
                    if not isinstance(all_metadata[k], list):
                        if all_metadata[k] == v:
                            continue
                        all_metadata[k] = [all_metadata[k], v]
                    else:
                        if v not in all_metadata[k]:
                            all_metadata[k].append(v)
        # logger.debug(f"All metadata: {all_metadata}")
        return result, all_metadata

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.config.input_config import InputConfig
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.messages import ConversationTurnResponseMessage
from aiperf.common.models import RequestRecord, Text, Turn
from aiperf.common.tokenizer import Tokenizer
from aiperf.parsers import InferenceResultParser


@pytest.fixture
def mock_tokenizer():
    tokenizer = MagicMock(spec=Tokenizer)
    tokenizer.encode.side_effect = lambda x: list(range(len(x.split())))
    return tokenizer


@pytest.fixture
def sample_turn():
    return Turn(
        role="user",
        texts=[
            Text(contents=["Hello world", "Test case"]),
            Text(contents=["Another input", "Final message"]),
        ],
    )


@pytest.fixture
def sample_turn_with_token_count():
    return Turn(
        role="user",
        texts=[
            Text(contents=["Hello world", "Test case"]),
            Text(contents=["Another input", "Final message"]),
        ],
        input_token_count=8,  # Pre-computed token count
    )


@pytest.fixture
def mock_turn_response(sample_turn):
    return ConversationTurnResponseMessage(
        service_id="test-service",
        turn=sample_turn,
    )


@pytest.fixture
def mock_turn_response_with_token_count(sample_turn_with_token_count):
    return ConversationTurnResponseMessage(
        service_id="test-service",
        turn=sample_turn_with_token_count,
    )


@pytest.fixture
def sample_request_record():
    return RequestRecord(conversation_id="cid", turn_index=0)


@pytest.fixture
def sample_request_record_with_token_count():
    return RequestRecord(
        conversation_id="cid",
        turn_index=0,
        input_token_count=12,  # Pre-computed in RequestRecord
    )


@pytest.fixture
def parser(mock_turn_response):
    with patch.object(InferenceResultParser, "__init__", lambda self, **kwargs: None):
        parser = InferenceResultParser(
            service_config=ServiceConfig(),
            user_config=UserConfig(
                endpoint=EndpointConfig(model_names=["test-model"]),
                input=InputConfig(),
            ),
        )
        parser.id = "test-parser"
        parser.conversation_request_client = MagicMock()
        parser.conversation_request_client.request = AsyncMock(
            return_value=mock_turn_response
        )
        return parser


@pytest.fixture
def parser_with_precomputed_tokens(mock_turn_response_with_token_count):
    with patch.object(InferenceResultParser, "__init__", lambda self, **kwargs: None):
        parser = InferenceResultParser(
            service_config=ServiceConfig(),
            user_config=UserConfig(
                endpoint=EndpointConfig(model_names=["test-model"]),
                input=InputConfig(),
            ),
        )
        parser.id = "test-parser"
        parser.conversation_request_client = MagicMock()
        parser.conversation_request_client.request = AsyncMock(
            return_value=mock_turn_response_with_token_count
        )
        return parser


@pytest.mark.asyncio
async def test_compute_input_token_count_from_request_record(
    parser, sample_request_record_with_token_count, mock_tokenizer
):
    """Test that pre-computed token counts from RequestRecord are used directly, avoiding dataset manager requests."""
    result = await parser.compute_input_token_count(
        sample_request_record_with_token_count, mock_tokenizer
    )

    assert result == 12  # Pre-computed token count from RequestRecord
    assert mock_tokenizer.encode.call_count == 0  # Tokenizer should not be called
    # Verify that no dataset manager request was made
    assert parser.conversation_request_client.request.call_count == 0


@pytest.mark.asyncio
async def test_compute_input_token_count_with_precomputed_tokens(
    parser_with_precomputed_tokens, sample_request_record, mock_tokenizer
):
    """Test that pre-computed token counts are used when available, avoiding tokenization."""
    result = await parser_with_precomputed_tokens.compute_input_token_count(
        sample_request_record, mock_tokenizer
    )

    assert result == 8  # Pre-computed token count
    assert mock_tokenizer.encode.call_count == 0  # Tokenizer should not be called


@pytest.mark.asyncio
async def test_compute_input_token_count_fallback_to_tokenization(
    parser, sample_request_record, mock_tokenizer
):
    """Test fallback to tokenization when no pre-computed token count is available."""
    result = await parser.compute_input_token_count(
        sample_request_record, mock_tokenizer
    )

    assert result == 8  # 4 strings × 2 words each
    assert (
        mock_tokenizer.encode.call_count == 4
    )  # Tokenizer should be called for each content

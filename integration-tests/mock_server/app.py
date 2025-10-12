# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""FastAPI server for integration testing with configurable latencies.

This mock server implements OpenAI-compatible endpoints with full Pydantic models
and support for reasoning tokens (e.g., o1 models).
"""

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from openai.types import CompletionUsage
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_chunk import Choice as ChunkChoice
from openai.types.chat.chat_completion_chunk import ChoiceDelta
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from openai.types.chat.completion_create_params import (
    CompletionCreateParams as ChatCompletionCreateParams,
)
from openai.types.completion import Completion
from openai.types.completion_choice import CompletionChoice as TextCompletionChoice
from openai.types.completion_create_params import (
    CompletionCreateParams as TextCompletionCreateParams,
)
from openai.types.completion_usage import CompletionTokensDetails
from openai.types.create_embedding_response import (
    CreateEmbeddingResponse,
    Embedding,
)
from openai.types.create_embedding_response import Usage as EmbeddingUsage
from openai.types.embedding_create_params import EmbeddingCreateParams

from .config import MockServerConfig
from .models import (
    ConfigureMessage,
    RankingResult,
    RankingsRequest,
    RankingsResponse,
)
from .tokenizer_service import tokenizer_service

logger = logging.getLogger(__name__)

server_config: MockServerConfig = MockServerConfig()
EMBEDDING_DIMENSIONS = 768


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Server configuration: %s", server_config.model_dump())
    yield


app = FastAPI(
    title="AIPerf Integration Test Server",
    description="FastAPI server with OpenAI-compatible endpoints and configurable latencies",
    version="1.0.0",
    lifespan=lifespan,
)


def create_request_id(prefix: str = "chatcmpl") -> str:
    return f"{prefix}-{uuid.uuid4()}"


def extract_user_content(messages: list[ChatCompletionMessageParam]) -> str:
    user_messages = []
    for msg in messages:
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue

        content = msg.get("content")
        if isinstance(content, str):
            user_messages.append(content)
        elif isinstance(content, list):
            user_messages.extend(
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            )
    return "\n".join(user_messages)


def build_completion_usage(
    prompt_tokens: int,
    completion_tokens: int,
    reasoning_tokens: int | None = None,
) -> CompletionUsage:
    total = prompt_tokens + completion_tokens
    if reasoning_tokens:
        return CompletionUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            completion_tokens_details=CompletionTokensDetails(
                reasoning_tokens=reasoning_tokens
            ),
        )
    return CompletionUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total,
    )


def calculate_reasoning_tokens(
    model: str,
    reasoning_effort: Literal["low", "medium", "high"] | None,
    override: int | None,
) -> int | None:
    if override is not None:
        return override
    if "o1" in model.lower() or "reasoning" in model.lower():
        effort_map = {"low": 100, "medium": 500, "high": 1000}
        return effort_map.get(reasoning_effort or "medium", 500)
    return None


async def sleep_until(target_time: float) -> None:
    remaining = target_time - perf_counter()
    if remaining > 0:
        await asyncio.sleep(remaining)


async def simulate_latency(start_time: float, num_tokens: int = 1) -> None:
    ttft_seconds = server_config.ttft / 1000.0
    itl_seconds = server_config.itl / 1000.0
    total_time = ttft_seconds + (num_tokens - 1) * itl_seconds
    await sleep_until(start_time + total_time)


async def stream_with_timing(
    tokens: list[str], start_time: float
) -> AsyncGenerator[tuple[int, str, float], None]:
    """Yields (index, token, target_time) with proper TTFT/ITL timing."""
    prev_time = start_time
    ttft_seconds = server_config.ttft / 1000.0
    itl_seconds = server_config.itl / 1000.0

    for i, token in enumerate(tokens):
        target = start_time + ttft_seconds if i == 0 else prev_time + itl_seconds
        await sleep_until(target)
        prev_time = target
        yield i, token, target


async def stream_chat_completion(
    tokens: list[str],
    start_time: float,
    request_id: str,
    created: int,
    model: str,
    prompt_tokens: int,
    reasoning_tokens: int | None,
    include_usage: bool = False,
) -> AsyncGenerator[str, None]:
    async for i, token, _ in stream_with_timing(tokens, start_time):
        delta = ChoiceDelta(content=token, role="assistant" if i == 0 else None)
        chunk = ChatCompletionChunk(
            id=request_id,
            object="chat.completion.chunk",
            created=created,
            model=model,
            choices=[
                ChunkChoice(
                    index=0,
                    delta=delta,
                    finish_reason="stop" if i == len(tokens) - 1 else None,
                )
            ],
        )
        yield f"data: {chunk.model_dump_json()}\n\n"

    if include_usage or prompt_tokens > 0 or reasoning_tokens:
        usage = build_completion_usage(prompt_tokens, len(tokens), reasoning_tokens)
        usage_chunk = ChatCompletionChunk(
            id=request_id,
            object="chat.completion.chunk",
            created=created,
            model=model,
            choices=[],
            usage=usage,
        )
        yield f"data: {usage_chunk.model_dump_json()}\n\n"

    yield "data: [DONE]\n\n"


async def stream_text_completion(
    tokens: list[str],
    start_time: float,
    request_id: str,
    created: int,
    model: str,
    prompt_tokens: int,
    reasoning_tokens: int | None,
    include_usage: bool = False,
) -> AsyncGenerator[str, None]:
    async for i, token, _ in stream_with_timing(tokens, start_time):
        is_last = i == len(tokens) - 1
        choice = TextCompletionChoice.model_construct(
            index=0,
            text=token,
            finish_reason="stop" if is_last else None,
        )
        chunk = Completion(
            id=request_id,
            object="text_completion",
            created=created,
            model=model,
            choices=[choice],
        )
        yield f"data: {chunk.model_dump_json(exclude_none=True)}\n\n"

    if include_usage or prompt_tokens > 0 or reasoning_tokens:
        usage = build_completion_usage(prompt_tokens, len(tokens), reasoning_tokens)
        usage_chunk = Completion(
            id=request_id,
            object="text_completion",
            created=created,
            model=model,
            choices=[],
            usage=usage,
        )
        yield f"data: {usage_chunk.model_dump_json()}\n\n"

    yield "data: [DONE]\n\n"


@app.post("/configure")
async def configure(request: ConfigureMessage):
    if request.itl is not None:
        server_config.itl = request.itl
    if request.ttft is not None:
        server_config.ttft = request.ttft
    return {"status": "configured", "config": server_config.model_dump()}


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionCreateParams):
    start_time = perf_counter()
    request_id = create_request_id("chatcmpl")
    created = int(time.time())

    model = str(request["model"])
    max_tokens = request.get("max_completion_tokens") or request.get("max_tokens")

    user_content = extract_user_content(request["messages"])
    tokens = tokenizer_service.tokenize(user_content, model)
    if max_tokens:
        tokens = tokens[:max_tokens]

    prompt_tokens = tokenizer_service.count_tokens(user_content, model)
    reasoning_tokens = calculate_reasoning_tokens(
        model, request.get("reasoning_effort"), request.get("reasoning_tokens")
    )

    if request.get("stream", False):
        stream_options = request.get("stream_options")
        include_usage = (
            stream_options.get("include_usage", False) if stream_options else False
        )
        return StreamingResponse(
            stream_chat_completion(
                tokens,
                start_time,
                request_id,
                created,
                model,
                prompt_tokens,
                reasoning_tokens,
                include_usage,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    await simulate_latency(start_time, len(tokens))
    return ChatCompletion(
        id=request_id,
        object="chat.completion",
        created=created,
        model=model,
        choices=[
            Choice(
                index=0,
                message=ChatCompletionMessage(
                    role="assistant", content="".join(tokens)
                ),
                finish_reason="stop",
            )
        ],
        usage=build_completion_usage(prompt_tokens, len(tokens), reasoning_tokens),
    )


@app.post("/v1/completions")
async def completions(request: TextCompletionCreateParams):
    start_time = perf_counter()
    request_id = create_request_id("cmpl")
    created = int(time.time())

    model = str(request["model"])
    prompt_input = request["prompt"]
    prompt = (
        prompt_input
        if isinstance(prompt_input, str)
        else "\n".join(str(p) for p in prompt_input if p is not None)
    )
    tokens = tokenizer_service.tokenize(prompt, model)
    if request.get("max_tokens"):
        tokens = tokens[: request["max_tokens"]]

    prompt_tokens = tokenizer_service.count_tokens(prompt, model)
    reasoning_tokens = request.get("reasoning_tokens")

    if request.get("stream", False):
        stream_options = request.get("stream_options")
        include_usage = (
            stream_options.get("include_usage", False) if stream_options else False
        )
        return StreamingResponse(
            stream_text_completion(
                tokens,
                start_time,
                request_id,
                created,
                model,
                prompt_tokens,
                reasoning_tokens,
                include_usage,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    await simulate_latency(start_time, len(tokens))
    return Completion(
        id=request_id,
        object="text_completion",
        created=created,
        model=model,
        choices=[
            TextCompletionChoice(index=0, text="".join(tokens), finish_reason="stop")
        ],
        usage=build_completion_usage(prompt_tokens, len(tokens), reasoning_tokens),
    )


@app.post("/v1/embeddings")
async def embeddings(request: EmbeddingCreateParams):
    await simulate_latency(perf_counter())

    model = str(request["model"])
    input_data = request["input"]
    inputs = (
        [input_data] if isinstance(input_data, str) else [str(i) for i in input_data]
    )

    embeddings_data = [
        Embedding(
            object="embedding",
            index=i,
            embedding=[
                float((hash(text) + j * 17) % 1000) / 1000.0 - 0.5
                for j in range(EMBEDDING_DIMENSIONS)
            ],
        )
        for i, text in enumerate(inputs)
    ]

    total_tokens = sum(tokenizer_service.count_tokens(text, model) for text in inputs)

    return CreateEmbeddingResponse(
        object="list",
        data=embeddings_data,
        model=model,
        usage=EmbeddingUsage(prompt_tokens=total_tokens, total_tokens=total_tokens),
    )


@app.post("/v1/ranking")
async def rankings(request: RankingsRequest):
    await simulate_latency(perf_counter())

    query_hash = hash(request.query.text)
    results = [
        RankingResult(
            index=i,
            relevance_score=float((query_hash ^ hash(passage.text)) % 1000) / 1000.0,
        )
        for i, passage in enumerate(request.passages)
    ]
    results.sort(key=lambda x: x.relevance_score, reverse=True)

    query_tokens = tokenizer_service.count_tokens(request.query.text, request.model)
    passage_tokens = sum(
        tokenizer_service.count_tokens(passage.text, request.model)
        for passage in request.passages
    )
    total_tokens = query_tokens + passage_tokens

    return RankingsResponse(
        id=create_request_id("rank"),
        model=request.model,
        rankings=results,
        usage=CompletionUsage(
            prompt_tokens=total_tokens,
            completion_tokens=0,
            total_tokens=total_tokens,
        ),
    )


@app.get("/health")
async def health_check():
    return {"status": "healthy", "config": server_config.model_dump()}


@app.get("/")
async def root():
    return {
        "message": "AIPerf Integration Test Server",
        "version": "1.0.0",
        "description": "OpenAI-compatible mock server with configurable latencies",
        "features": [
            "Chat completions (streaming & non-streaming)",
            "Text completions (streaming & non-streaming)",
            "Embeddings",
            "Rankings/Reranking",
            "Reasoning tokens (o1 models)",
            "Configurable TTFT and ITL",
        ],
        "endpoints": {
            "chat_completions": "/v1/chat/completions",
            "completions": "/v1/completions",
            "embeddings": "/v1/embeddings",
            "ranking": "/v1/ranking",
            "health": "/health",
            "configure": "/configure",
        },
        "config": server_config.model_dump(),
    }

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""FastAPI server for integration testing with configurable latencies."""

import asyncio
import json
import logging
import os
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from openai.types import CompletionUsage
from openai.types.chat.chat_completion import ChatCompletion, Choice
from openai.types.chat.chat_completion_chunk import (
    ChatCompletionChunk,
    ChoiceDelta,
)
from openai.types.chat.chat_completion_chunk import (
    Choice as StreamChoice,
)
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.completion import Completion
from openai.types.completion_choice import CompletionChoice as TextCompletionChoice
from openai.types.create_embedding_response import (
    CreateEmbeddingResponse,
    Embedding,
)
from openai.types.create_embedding_response import (
    Usage as EmbeddingUsage,
)
from pydantic import BaseModel

from .config import MockServerConfig
from .models import (
    ConfigureMessage,
    RankingResult,
    RankingsRequest,
    RankingsResponse,
)
from .tokenizer_service import tokenizer_service

logger = logging.getLogger(__name__)

# Global server configuration
server_config: MockServerConfig = MockServerConfig()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize tokenizers and other startup tasks."""
    logger.info("Server configuration: %s", server_config.model_dump())

    if server_config.tokenizer_models:
        logger.info(f"Pre-loading tokenizer models: {server_config.tokenizer_models}")
        tokenizer_service.load_tokenizers(server_config.tokenizer_models)
        logger.info("Tokenizer models loaded successfully")

    yield


app = FastAPI(
    title="AIPerf Integration Test Server",
    description="FastAPI server that supports OpenAI-compatible endpoints with configurable latencies",
    version="1.0.0",
    lifespan=lifespan,
)


def set_server_config(config: MockServerConfig) -> None:
    """Set the global server configuration."""
    global server_config
    server_config = config

    # TODO: This is a hack to get the config into the environment variables
    # in order to run multiple worker instances
    os.environ["MOCK_SERVER_TOKENIZER_MODELS"] = json.dumps(config.tokenizer_models)
    os.environ["MOCK_SERVER_TTFT"] = str(config.ttft)
    os.environ["MOCK_SERVER_ITL"] = str(config.itl)
    os.environ["MOCK_SERVER_LOG_LEVEL"] = config.log_level
    os.environ["MOCK_SERVER_HOST"] = config.host
    os.environ["MOCK_SERVER_PORT"] = str(config.port)
    os.environ["MOCK_SERVER_WORKERS"] = str(config.workers)
    os.environ["MOCK_SERVER_ACCESS_LOGS"] = str(config.access_logs)


def extract_user_prompt_from_messages(messages: list[dict]) -> str:
    """Extract the user prompt from chat messages."""
    # Combine all user messages for tokenization
    user_messages = []
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                user_messages.append(content)
            elif isinstance(content, list):
                # Handle multimodal content
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        user_messages.append(item.get("text", ""))
    return "\n".join(user_messages) if user_messages else ""


async def generate_streaming_chat_response(
    messages: list[dict],
    model: str,
    tokens: list[str],
    request_id: str,
    created_timestamp: int,
    start_time: float,
) -> AsyncGenerator[str, None]:
    """Generate streaming chat completion response."""
    previous_time = start_time

    # Send tokens one by one
    for i, token in enumerate(tokens):
        if i == 0:
            # Wait for time to first token with precise timing
            target_time = start_time + (server_config.ttft / 1000.0)
        if i > 0:
            target_time = previous_time + (server_config.itl / 1000.0)

        to_sleep = target_time - perf_counter()
        if to_sleep > 0:
            await asyncio.sleep(to_sleep)

        # Update previous time to calculate next inter-token latency
        previous_time = target_time

        # Create streaming response chunk
        chunk = ChatCompletionChunk(
            id=request_id,
            object="chat.completion.chunk",
            created=created_timestamp,
            model=model,
            choices=[
                StreamChoice(
                    index=0,
                    delta=ChoiceDelta(
                        content=token, role="assistant" if i == 0 else None
                    ),
                    finish_reason="stop" if i == len(tokens) - 1 else None,
                )
            ],
        )

        yield f"data: {chunk.model_dump_json()}\n\n"

    yield "data: [DONE]\n\n"


async def generate_streaming_completion_response(
    model: str,
    tokens: list[str],
    request_id: str,
    created_timestamp: int,
    start_time: float,
) -> AsyncGenerator[str, None]:
    """Generate streaming text completion response."""
    previous_time = start_time

    # Send tokens one by one
    for i, token in enumerate(tokens):
        if i == 0:
            # Wait for time to first token with precise timing
            target_time = start_time + (server_config.ttft / 1000.0)
        if i > 0:
            target_time = previous_time + (server_config.itl / 1000.0)

        to_sleep = target_time - perf_counter()
        if to_sleep > 0:
            await asyncio.sleep(to_sleep)

        # Update previous time to calculate next inter-token latency
        previous_time = target_time

        # Create streaming response chunk as dict (no official Completion streaming type)
        chunk = {
            "id": request_id,
            "object": "text_completion",
            "created": created_timestamp,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "text": token,
                    "finish_reason": "stop" if i == len(tokens) - 1 else None,
                }
            ],
        }

        yield f"data: {json.dumps(chunk)}\n\n"

    yield "data: [DONE]\n\n"


@app.post("/configure")
async def configure(request: ConfigureMessage):
    """Configure the server."""
    if request.itl is not None:
        server_config.itl = request.itl
    if request.ttft is not None:
        server_config.ttft = request.ttft
    if request.tokenizer_models is not None:
        logger.info(f"Loading tokenizer models: {request.tokenizer_models}")
        tokenizer_service.load_tokenizers(request.tokenizer_models)
        logger.info("Tokenizer models loaded successfully")

    return {"status": "configured", "config": server_config.model_dump()}


class ChatCompletionRequest(BaseModel):
    """Chat completion request (using dict for flexibility)."""

    model: str
    messages: list[dict]
    max_completion_tokens: int | None = None
    max_tokens: int | None = None  # Legacy field
    stream: bool = False


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """Handle chat completion requests."""
    start_time = perf_counter()
    request_id = f"chatcmpl-{uuid.uuid4()}"
    created_timestamp = int(time.time())

    user_prompt = extract_user_prompt_from_messages(request.messages)
    try:
        # Tokenize the user prompt using the requested model's tokenizer
        tokens = tokenizer_service.tokenize(user_prompt, request.model)
    except Exception as e:
        # If the tokenizer fails, return a 404 error to simulate model not found
        raise HTTPException(
            status_code=404,
            detail="Model Not Found",
        ) from e

    # Handle both max_completion_tokens and legacy max_tokens
    max_tokens = request.max_completion_tokens or request.max_tokens
    if max_tokens is not None:
        tokens = tokens[:max_tokens]

    if request.stream:
        # Return streaming response
        return StreamingResponse(
            generate_streaming_chat_response(
                request.messages,
                request.model,
                tokens,
                request_id,
                created_timestamp,
                start_time,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
    else:
        # Return non-streaming response

        # Simulate processing time for all tokens with precise timing
        ttft_time = start_time + (server_config.ttft / 1000.0)
        token_processing_time = (len(tokens) - 1) * server_config.itl / 1000.0

        target_time = ttft_time + token_processing_time

        if target_time > perf_counter():
            await asyncio.sleep(target_time - perf_counter())

        # Reconstruct the response text
        response_text = "".join(tokens)

        # Count tokens for usage statistics
        prompt_tokens = tokenizer_service.count_tokens(user_prompt, request.model)
        completion_tokens = len(tokens)

        response = ChatCompletion(
            id=request_id,
            object="chat.completion",
            created=created_timestamp,
            model=request.model,
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant",
                        content=response_text,
                    ),
                    finish_reason="stop",
                )
            ],
            usage=CompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )

        return response


class CompletionRequest(BaseModel):
    """Text completion request."""

    model: str
    prompt: str | list[str]
    max_tokens: int | None = None
    stream: bool = False


@app.post("/v1/completions")
async def completions(request: CompletionRequest):
    """Handle text completion requests."""
    start_time = perf_counter()
    request_id = f"cmpl-{uuid.uuid4()}"
    created_timestamp = int(time.time())

    # Handle both single string and list of strings
    prompt = (
        request.prompt if isinstance(request.prompt, str) else "\n".join(request.prompt)
    )

    try:
        # Tokenize the prompt using the requested model's tokenizer
        tokens = tokenizer_service.tokenize(prompt, request.model)
    except Exception as e:
        # If the tokenizer fails, return a 404 error to simulate model not found
        raise HTTPException(
            status_code=404,
            detail="Model Not Found",
        ) from e

    if request.max_tokens is not None:
        tokens = tokens[: request.max_tokens]

    if request.stream:
        # Return streaming response
        return StreamingResponse(
            generate_streaming_completion_response(
                request.model,
                tokens,
                request_id,
                created_timestamp,
                start_time,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
    else:
        # Return non-streaming response

        # Simulate processing time for all tokens with precise timing
        ttft_time = start_time + (server_config.ttft / 1000.0)
        token_processing_time = (len(tokens) - 1) * server_config.itl / 1000.0

        target_time = ttft_time + token_processing_time

        if target_time > perf_counter():
            await asyncio.sleep(target_time - perf_counter())

        # Reconstruct the response text
        response_text = "".join(tokens)

        # Count tokens for usage statistics
        prompt_tokens = tokenizer_service.count_tokens(prompt, request.model)
        completion_tokens = len(tokens)

        response = Completion(
            id=request_id,
            object="text_completion",
            created=created_timestamp,
            model=request.model,
            choices=[
                TextCompletionChoice(
                    index=0,
                    text=response_text,
                    finish_reason="stop",
                )
            ],
            usage=CompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )

        return response


class EmbeddingsRequest(BaseModel):
    """Embeddings request."""

    model: str
    input: str | list[str]


@app.post("/v1/embeddings")
async def embeddings(request: EmbeddingsRequest):
    """Handle embeddings requests."""
    start_time = perf_counter()

    # Handle both single string and list of strings
    inputs = [request.input] if isinstance(request.input, str) else request.input

    # For embeddings, we simulate processing time but don't use tokens
    # Just simulate a constant latency based on TTFT
    target_time = start_time + (server_config.ttft / 1000.0)
    if target_time > perf_counter():
        await asyncio.sleep(target_time - perf_counter())

    # Generate mock embeddings (768-dimensional vectors with random-ish values)
    # Using a simple deterministic approach based on input hash for consistency
    embedding_list = []
    for i, text in enumerate(inputs):
        # Create a simple deterministic embedding based on text hash
        hash_val = hash(text)
        # Generate 768 dimensions (common embedding size)
        embedding_values = [
            float((hash_val + j * 17) % 1000) / 1000.0 - 0.5 for j in range(768)
        ]

        embedding_list.append(
            Embedding(
                object="embedding",
                index=i,
                embedding=embedding_values,
            )
        )

    # Count tokens for usage (if tokenizer is available)
    total_tokens = 0
    try:
        for text in inputs:
            total_tokens += tokenizer_service.count_tokens(text, request.model)
    except Exception:
        # If tokenizer fails, estimate based on text length
        total_tokens = sum(len(text.split()) for text in inputs)

    response = CreateEmbeddingResponse(
        object="list",
        data=embedding_list,
        model=request.model,
        usage=EmbeddingUsage(
            prompt_tokens=total_tokens,
            total_tokens=total_tokens,
        ),
    )

    return response


@app.post("/v1/ranking")
async def rankings(request: RankingsRequest):
    """Handle rankings/reranking requests."""
    start_time = perf_counter()
    request_id = f"rank-{uuid.uuid4()}"

    # For rankings, we simulate processing time but don't use tokens
    # Just simulate a constant latency based on TTFT
    target_time = start_time + (server_config.ttft / 1000.0)
    if target_time > perf_counter():
        await asyncio.sleep(target_time - perf_counter())

    # Generate mock ranking scores
    # Use a simple deterministic approach based on query and passage hashes
    query_hash = hash(request.query.text)
    ranking_results = []

    for i, passage in enumerate(request.passages):
        passage_hash = hash(passage.text)
        # Create a relevance score between 0 and 1 based on hashes
        relevance_score = float((query_hash ^ passage_hash) % 1000) / 1000.0

        ranking_results.append(
            RankingResult(
                index=i,
                relevance_score=relevance_score,
            )
        )

    # Sort by relevance score descending
    ranking_results.sort(key=lambda x: x.relevance_score, reverse=True)

    # Count tokens for usage (if tokenizer is available)
    total_tokens = 0
    try:
        total_tokens += tokenizer_service.count_tokens(
            request.query.text, request.model
        )
        for passage in request.passages:
            total_tokens += tokenizer_service.count_tokens(passage.text, request.model)
    except Exception:
        # If tokenizer fails, estimate based on text length
        total_tokens = len(request.query.text.split())
        total_tokens += sum(len(p.text.split()) for p in request.passages)

    response = RankingsResponse(
        id=request_id,
        model=request.model,
        rankings=ranking_results,
        usage=CompletionUsage(
            prompt_tokens=total_tokens,
            completion_tokens=0,
            total_tokens=total_tokens,
        ),
    )

    return response


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "config": server_config.model_dump()}


@app.get("/")
async def root():
    """Root endpoint with server information."""
    return {
        "message": "AIPerf Integration Test Server",
        "version": "1.0.0",
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

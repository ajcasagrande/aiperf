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

from .config import MockServerConfig
from .models import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionStreamChoice,
    ChatCompletionStreamResponse,
    ChatMessage,
    ConfigureMessage,
    ResponseOutputMessage,
    ResponseOutputText,
    ResponsesRequest,
    ResponsesResponse,
    ResponsesStreamEvent,
    Role,
    Usage,
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
    description="FastAPI server that echoes prompts token by token with configurable latencies",
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


def extract_user_prompt(messages: list[ChatMessage]) -> str:
    """Extract the user prompt from chat messages."""
    # Combine all user messages for tokenization
    user_messages = [msg.content for msg in messages if msg.role == Role.USER]
    return "\n".join(user_messages) if user_messages else ""


def extract_input_text(input_data: str | list[str]) -> str:
    """Extract text from Responses API input field."""
    if isinstance(input_data, str):
        return input_data
    elif isinstance(input_data, list):
        return "\n".join(input_data)
    return ""


async def generate_streaming_response(
    request: ChatCompletionRequest,
    input_tokens: list,
    request_id: str,
    created_timestamp: int,
    start_time: float,
) -> AsyncGenerator[str, None]:
    """Generate streaming chat completion response."""

    previous_time = start_time
    # Send tokens one by one
    for i, token in enumerate(input_tokens):
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
        chunk = ChatCompletionStreamResponse(
            id=request_id,
            created=created_timestamp,
            model=request.model,
            choices=[
                ChatCompletionStreamChoice(
                    index=0,
                    delta={"content": token},
                    finish_reason="stop" if i == len(input_tokens) - 1 else None,
                )
            ],
        )

        yield f"data: {chunk.model_dump_json()}\n\n"

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


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """Handle chat completion requests."""
    start_time = perf_counter()
    request_id = f"chatcmpl-{uuid.uuid4()}"
    created_timestamp = int(time.time())

    user_prompt = extract_user_prompt(request.messages)
    try:
        # Tokenize the user prompt using the requested model's tokenizer
        tokens = tokenizer_service.tokenize(user_prompt, request.model)
    except Exception as e:
        # If the tokenizer fails, return a 404 error to simulate model not found
        raise HTTPException(
            status_code=404,
            detail="Model Not Found",
        ) from e

    if request.max_completion_tokens is not None:
        tokens = tokens[: request.max_completion_tokens]

    if request.stream:
        # Return streaming response
        return StreamingResponse(
            generate_streaming_response(
                request,
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

        response = ChatCompletionResponse(
            id=request_id,
            created=created_timestamp,
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role=Role.ASSISTANT, content=response_text),
                    finish_reason="stop",
                )
            ],
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )

        return response


async def generate_streaming_responses_api(
    request: ResponsesRequest,
    input_tokens: list,
    request_id: str,
    message_id: str,
    created_timestamp: int,
    start_time: float,
) -> AsyncGenerator[str, None]:
    """Generate streaming response for Responses API."""

    # Event: response.created
    response_created = ResponsesStreamEvent(
        type="response.created",
        response={
            "id": request_id,
            "object": "response",
            "created_at": created_timestamp,
            "status": "in_progress",
            "model": request.model,
            "output": [],
        },
    )
    yield f"event: response.created\ndata: {response_created.model_dump_json()}\n\n"

    # Event: response.in_progress
    response_in_progress = ResponsesStreamEvent(
        type="response.in_progress",
        response={
            "id": request_id,
            "object": "response",
            "created_at": created_timestamp,
            "status": "in_progress",
            "model": request.model,
            "output": [],
        },
    )
    yield f"event: response.in_progress\ndata: {response_in_progress.model_dump_json()}\n\n"

    # Event: response.output_item.added
    output_item_added = ResponsesStreamEvent(
        type="response.output_item.added",
        output_index=0,
        item={
            "id": message_id,
            "type": "message",
            "status": "in_progress",
            "role": "assistant",
            "content": [],
        },
    )
    yield f"event: response.output_item.added\ndata: {output_item_added.model_dump_json()}\n\n"

    # Event: response.content_part.added
    content_part_added = ResponsesStreamEvent(
        type="response.content_part.added",
        item_id=message_id,
        output_index=0,
        content_index=0,
        part={"type": "output_text", "text": "", "annotations": []},
    )
    yield f"event: response.content_part.added\ndata: {content_part_added.model_dump_json()}\n\n"

    previous_time = start_time
    full_text = ""

    # Send tokens one by one with delta events
    for i, token in enumerate(input_tokens):
        if i == 0:
            target_time = start_time + (server_config.ttft / 1000.0)
        if i > 0:
            target_time = previous_time + (server_config.itl / 1000.0)

        to_sleep = target_time - perf_counter()
        if to_sleep > 0:
            await asyncio.sleep(to_sleep)

        previous_time = target_time
        full_text += token

        # Event: response.output_text.delta
        delta_event = ResponsesStreamEvent(
            type="response.output_text.delta",
            item_id=message_id,
            output_index=0,
            content_index=0,
            delta=token,
        )
        yield f"event: response.output_text.delta\ndata: {delta_event.model_dump_json()}\n\n"

    # Event: response.output_text.done
    text_done = ResponsesStreamEvent(
        type="response.output_text.done",
        item_id=message_id,
        output_index=0,
        content_index=0,
        text=full_text,
    )
    yield f"event: response.output_text.done\ndata: {text_done.model_dump_json()}\n\n"

    # Event: response.content_part.done
    content_part_done = ResponsesStreamEvent(
        type="response.content_part.done",
        item_id=message_id,
        output_index=0,
        content_index=0,
        part={"type": "output_text", "text": full_text, "annotations": []},
    )
    yield f"event: response.content_part.done\ndata: {content_part_done.model_dump_json()}\n\n"

    # Event: response.output_item.done
    output_item_done = ResponsesStreamEvent(
        type="response.output_item.done",
        output_index=0,
        item={
            "id": message_id,
            "type": "message",
            "status": "completed",
            "role": "assistant",
            "content": [{"type": "output_text", "text": full_text, "annotations": []}],
        },
    )
    yield f"event: response.output_item.done\ndata: {output_item_done.model_dump_json()}\n\n"

    # Event: response.completed
    response_completed = ResponsesStreamEvent(
        type="response.completed",
        response={
            "id": request_id,
            "object": "response",
            "created_at": created_timestamp,
            "status": "completed",
            "model": request.model,
            "output": [
                {
                    "id": message_id,
                    "type": "message",
                    "status": "completed",
                    "role": "assistant",
                    "content": [
                        {"type": "output_text", "text": full_text, "annotations": []}
                    ],
                }
            ],
            "usage": {
                "input_tokens": len(input_tokens),
                "output_tokens": len(input_tokens),
                "total_tokens": len(input_tokens) * 2,
            },
        },
    )
    yield f"event: response.completed\ndata: {response_completed.model_dump_json()}\n\n"


@app.post("/v1/responses")
async def responses(request: ResponsesRequest):
    """Handle Responses API requests."""
    start_time = perf_counter()
    request_id = f"resp_{uuid.uuid4().hex}"
    message_id = f"msg_{uuid.uuid4().hex}"
    created_timestamp = int(time.time())

    input_text = extract_input_text(request.input)
    try:
        # Tokenize the input using the requested model's tokenizer
        tokens = tokenizer_service.tokenize(input_text, request.model)
    except Exception as e:
        # If the tokenizer fails, return a 404 error to simulate model not found
        raise HTTPException(
            status_code=404,
            detail="Model Not Found",
        ) from e

    if request.max_output_tokens is not None:
        tokens = tokens[: request.max_output_tokens]

    if request.stream:
        # Return streaming response
        return StreamingResponse(
            generate_streaming_responses_api(
                request,
                tokens,
                request_id,
                message_id,
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
        input_token_count = tokenizer_service.count_tokens(input_text, request.model)
        output_token_count = len(tokens)

        response = ResponsesResponse(
            id=request_id,
            created_at=created_timestamp,
            model=request.model,
            output=[
                ResponseOutputMessage(
                    id=message_id,
                    content=[ResponseOutputText(text=response_text)],
                )
            ],
            usage=Usage(
                prompt_tokens=input_token_count,
                completion_tokens=output_token_count,
                total_tokens=input_token_count + output_token_count,
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
            "responses": "/v1/responses",
            "health": "/health",
            "configure": "/configure",
        },
        "config": server_config.model_dump(),
    }

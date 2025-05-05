#!/usr/bin/env python3
"""
OpenAI API mock server implementation.
This mock server provides simulated OpenAI API responses for testing purposes.
"""

import argparse
import json
import logging
import time
import uuid
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Request, Response, status
import uvicorn

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("mock_server")

app = FastAPI(title="OpenAI API Mock Server")


@app.get("/")
async def root():
    """Root endpoint that returns basic info about the mock server."""
    return {
        "message": "OpenAI API Mock Server is running",
        "endpoints": [
            "/chat/completions",
            "/models",
            "/completions",
            "/embeddings",
        ],
    }


@app.post("/chat/completions")
async def chat_completions(request: Request):
    """Mock implementation of the OpenAI Chat Completions API."""
    body = await request.json()
    logger.info(f"Received request to /chat/completions: {body}")

    # Extract parameters from request
    messages = body.get("messages", [])
    model = body.get("model", "gpt-3.5-turbo")
    stream = body.get("stream", False)
    temperature = body.get("temperature", 0.7)
    max_tokens = body.get("max_tokens", 256)

    # Get the last user message to generate a response
    last_message = next(
        (m for m in reversed(messages) if m.get("role") == "user"), None
    )
    prompt = last_message.get("content", "") if last_message else "Hello"

    # Create response ID
    response_id = f"chatcmpl-{str(uuid.uuid4())[:8]}"
    created_time = int(time.time())

    if stream:
        # Return a streaming response
        return Response(
            content=generate_streaming_response(
                prompt, response_id, model, created_time
            ),
            media_type="text/event-stream",
        )
    else:
        # Return a standard response
        response = {
            "id": response_id,
            "object": "chat.completion",
            "created": created_time,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": generate_mock_response(prompt),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": len(
                    " ".join([m.get("content", "") for m in messages]).split()
                ),
                "completion_tokens": 50,
                "total_tokens": len(
                    " ".join([m.get("content", "") for m in messages]).split()
                )
                + 50,
            },
        }

        return response


@app.get("/models")
async def models():
    """Mock implementation of the OpenAI Models API."""
    return {
        "object": "list",
        "data": [
            {
                "id": "gpt-4",
                "object": "model",
                "created": 1687882410,
                "owned_by": "openai",
            },
            {
                "id": "gpt-4-turbo",
                "object": "model",
                "created": 1687882410,
                "owned_by": "openai",
            },
            {
                "id": "gpt-3.5-turbo",
                "object": "model",
                "created": 1677610602,
                "owned_by": "openai",
            },
            {
                "id": "text-embedding-ada-002",
                "object": "model",
                "created": 1671217299,
                "owned_by": "openai-internal",
            },
        ],
    }


@app.post("/completions")
async def completions(request: Request):
    """Mock implementation of the OpenAI Completions API."""
    body = await request.json()
    logger.info(f"Received request to /completions: {body}")

    # Extract parameters from request
    prompt = body.get("prompt", "")
    model = body.get("model", "text-davinci-003")
    stream = body.get("stream", False)

    # Create response ID
    response_id = f"cmpl-{str(uuid.uuid4())[:8]}"
    created_time = int(time.time())

    if isinstance(prompt, list):
        prompt = prompt[0] if prompt else ""

    response = {
        "id": response_id,
        "object": "text_completion",
        "created": created_time,
        "model": model,
        "choices": [
            {
                "text": generate_mock_response(prompt),
                "index": 0,
                "finish_reason": "stop",
                "logprobs": None,
            }
        ],
        "usage": {
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": 50,
            "total_tokens": len(prompt.split()) + 50,
        },
    }

    return response


@app.post("/embeddings")
async def embeddings(request: Request):
    """Mock implementation of the OpenAI Embeddings API."""
    body = await request.json()
    logger.info(f"Received request to /embeddings: {body}")

    # Extract parameters from request
    input_text = body.get("input", "")
    model = body.get("model", "text-embedding-ada-002")

    # Handle both string and list inputs
    if isinstance(input_text, str):
        inputs = [input_text]
    else:
        inputs = input_text

    # Generate mock embeddings
    data = []
    for i, text in enumerate(inputs):
        # Generate a deterministic but seemingly random embedding vector
        # Real embedding vectors are typically normalized to length 1
        vector = generate_mock_embedding(text, dimension=1536)
        data.append(
            {
                "object": "embedding",
                "embedding": vector,
                "index": i,
            }
        )

    response = {
        "object": "list",
        "data": data,
        "model": model,
        "usage": {
            "prompt_tokens": sum(len(text.split()) for text in inputs),
            "total_tokens": sum(len(text.split()) for text in inputs),
        },
    }

    return response


# Helper functions
def generate_mock_response(prompt: str) -> str:
    """Generate a mock response based on the prompt."""
    # Extract the first 20 characters of the prompt to personalize the response
    prompt_start = prompt[:20].strip()

    responses = [
        f"This is a mock response to '{prompt_start}...'. In a real API call, you would receive a thoughtful answer.",
        f"Mock server received: '{prompt_start}...'. Here's a simulated response for testing purposes.",
        f"Testing mode active. Your prompt '{prompt_start}...' would normally receive a detailed response.",
        f"Mock API response: I've processed your request about '{prompt_start}...' and generated this test response.",
    ]

    # Use prompt length as a deterministic way to select a response
    index = len(prompt) % len(responses)
    return responses[index]


def generate_streaming_response(
    prompt: str, response_id: str, model: str, created_time: int
) -> str:
    """Generate a mock streaming response."""
    mock_content = generate_mock_response(prompt)
    words = mock_content.split()

    chunks = []

    # First chunk with role
    first_chunk = {
        "id": response_id,
        "object": "chat.completion.chunk",
        "created": created_time,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant"},
                "finish_reason": None,
            }
        ],
    }
    chunks.append(f"data: {json.dumps(first_chunk)}\n\n")

    # Word by word chunks
    for i, word in enumerate(words):
        content_chunk = {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": created_time,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": word + " "},
                    "finish_reason": None,
                }
            ],
        }
        chunks.append(f"data: {json.dumps(content_chunk)}\n\n")

    # Final chunk
    final_chunk = {
        "id": response_id,
        "object": "chat.completion.chunk",
        "created": created_time,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    }
    chunks.append(f"data: {json.dumps(final_chunk)}\n\n")
    chunks.append("data: [DONE]\n\n")

    return "".join(chunks)


def generate_mock_embedding(text: str, dimension: int = 1536) -> List[float]:
    """Generate a deterministic mock embedding vector from text."""
    import hashlib

    # Create a deterministic hash from the text
    hash_object = hashlib.md5(text.encode())
    hash_hex = hash_object.hexdigest()

    # Use the hash to seed a random number generator
    import random

    random.seed(hash_hex)

    # Generate vector components
    vector = [random.uniform(-1, 1) for _ in range(dimension)]

    # Normalize to unit length
    magnitude = sum(x * x for x in vector) ** 0.5
    normalized = [x / magnitude for x in vector]

    return normalized


# Handle any other OpenAI API paths with 404
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def catch_all(path: str, request: Request):
    """Catch-all endpoint for unimplemented API paths."""
    try:
        body = await request.json()
        logger.info(f"Received request to unimplemented endpoint /{path}: {body}")
    except:
        logger.info(f"Received request to unimplemented endpoint /{path}")

    content = {
        "error": "Not Found",
        "message": f"Endpoint /{path} not implemented in mock server",
    }
    return Response(
        content=json.dumps(content),
        status_code=status.HTTP_404_NOT_FOUND,
        media_type="application/json",
    )


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run the OpenAI API mock server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    args = parser.parse_args()

    logger.info(f"Starting OpenAI API mock server on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)

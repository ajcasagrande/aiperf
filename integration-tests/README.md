<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# AI Performance Integration Test Server

A FastAPI server that implements OpenAI-compatible chat completions API for integration testing. The server echoes user prompts back token by token with configurable latencies, using the actual tokenizer from the requested model.

## Features

- **OpenAI-compatible API**: Implements `/v1/chat/completions` endpoint
- **Token-by-token echoing**: Uses the actual tokenizer from the requested model
- **Streaming and non-streaming**: Supports both `stream: true` and `stream: false`
- **Configurable latencies**:
  - Time to first token latency (TTFT)
  - Inter-token latency (ITL)
- **Precise timing**: Uses `perf_counter` for accurate latency simulation
- **Flexible configuration**: Environment variables and command-line arguments
- **Model-specific tokenization**: Automatically loads tokenizers for different models

## Installation

```bash
cd integration-tests
pip install -e .
```

Or with development dependencies:
```bash
pip install -e ".[dev]"
```

## Usage

### Command Line

```bash
# Basic usage
integration-server

# Custom configuration
integration-server \
  --port 8080 \
  --time-to-first-token-ms 30 \
  --inter-token-latency-ms 10 \
  --host 127.0.0.1

# With environment variables
export SERVER_PORT=8080
export TIME_TO_FIRST_TOKEN_MS=30
export INTER_TOKEN_LATENCY_MS=10
integration-server
```

### Environment Variables

- `SERVER_PORT`: Port to run the server on (default: 8000)
- `SERVER_HOST`: Host to bind to (default: 0.0.0.0)
- `TIME_TO_FIRST_TOKEN_MS`: Time to first token latency in milliseconds (default: 100.0)
- `INTER_TOKEN_LATENCY_MS`: Inter-token latency in milliseconds (default: 50.0)

### API Usage

#### Non-streaming

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [
      {"role": "user", "content": "Hello, world!"}
    ],
    "max_tokens": 10,
    "stream": false
  }'
```

#### Streaming

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [
      {"role": "user", "content": "Hello, world!"}
    ],
    "max_tokens": 10,
    "stream": true
  }'
```

### Health Check

```bash
curl http://localhost:8000/health
```

## Configuration Options

| Parameter | CLI Flag | Environment Variable | Default | Description |
|-----------|----------|---------------------|---------|-------------|
| Port | `--port` | `SERVER_PORT` | 8000 | Server port |
| Host | `--host` | `SERVER_HOST` | 0.0.0.0 | Server host |
| TTFT | `--time-to-first-token-ms` | `TIME_TO_FIRST_TOKEN_MS` | 100.0 | Time to first token (ms) |
| ITL | `--inter-token-latency-ms` | `INTER_TOKEN_LATENCY_MS` | 50.0 | Inter-token latency (ms) |

## How It Works

1. **Request Processing**: The server receives a chat completion request
2. **Tokenization**: Uses the model-specific tokenizer to tokenize the user prompt
3. **Token Limit**: Respects the `max_tokens` parameter if specified
4. **Latency Simulation**:
   - Waits for the configured TTFT before sending the first token
   - Waits for the configured ITL between subsequent tokens
5. **Response**: Echoes back the tokenized prompt either as:
   - A complete response (non-streaming)
   - Token-by-token chunks (streaming)

## Supported Models

The server automatically loads tokenizers for any model supported by Hugging Face Transformers. If a tokenizer fails to load, it falls back to GPT-2.

Common models:
- `gpt-3.5-turbo` (uses GPT-2 tokenizer as fallback)
- `gpt-4` (uses GPT-2 tokenizer as fallback)
- `microsoft/DialoGPT-large`
- `facebook/blenderbot-400M-distill`
- Any HuggingFace model with a tokenizer

## Development

### Running Tests

```bash
pytest
```

### Code Structure

```
server/
├── __init__.py          # Package initialization
├── app.py              # FastAPI application
├── config.py           # Configuration management
├── main.py             # CLI entry point
├── models.py           # Pydantic models
└── tokenizer_service.py # Tokenizer management
```

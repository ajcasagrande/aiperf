#!/bin/bash
# Start AIPerf with a mock OpenAI server and enhanced components

set -e

# Default values
CONFIG_FILE="aiperf/config/examples/openai_example.yaml"
MOCK_PORT=8000
DURATION=60
MOCK_SERVER_PID=""
MOCK_DELAY_MIN=0.1
MOCK_DELAY_MAX=1.0
MOCK_ERROR_RATE=0.05

# Parse command line arguments
while getopts "c:p:d:m:M:e:vh" opt; do
  case $opt in
    c) CONFIG_FILE=$OPTARG ;;
    p) MOCK_PORT=$OPTARG ;;
    d) DURATION=$OPTARG ;;
    m) MOCK_DELAY_MIN=$OPTARG ;;
    M) MOCK_DELAY_MAX=$OPTARG ;;
    e) MOCK_ERROR_RATE=$OPTARG ;;
    v) VERBOSE="-v" ;;
    h) 
      echo "Usage: $0 [options]"
      echo "Options:"
      echo "  -c CONFIG_FILE  Path to AIPerf config file (default: aiperf/config/examples/openai_example.yaml)"
      echo "  -p MOCK_PORT    Port for mock OpenAI server (default: 8000)"
      echo "  -d DURATION     Duration in seconds to run benchmark (default: 60)"
      echo "  -m DELAY_MIN    Minimum delay for mock responses in seconds (default: 0.1)"
      echo "  -M DELAY_MAX    Maximum delay for mock responses in seconds (default: 1.0)"
      echo "  -e ERROR_RATE   Error rate for mock responses (default: 0.05)"
      echo "  -v              Enable verbose logging"
      echo "  -h              Show this help message"
      exit 0
      ;;
    *) echo "Invalid option: -$OPTARG" >&2; exit 1 ;;
  esac
done

# Function to cleanup on exit
cleanup() {
  echo "Cleaning up..."
  if [ -n "$MOCK_SERVER_PID" ]; then
    echo "Stopping mock OpenAI server (PID: $MOCK_SERVER_PID)"
    kill $MOCK_SERVER_PID 2>/dev/null || true
  fi
  echo "Exiting..."
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Check for Python
if ! command -v python3 &> /dev/null; then
  echo "Python 3 is required but not installed"
  exit 1
fi

# Install required packages
echo "Checking dependencies..."
python3 -m pip install -q pyyaml fastapi uvicorn pydantic tiktoken

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
  echo "Config file not found: $CONFIG_FILE"
  exit 1
fi

# Modify the config to use the mock server
echo "Modifying config to use mock server..."
TEMP_CONFIG="/tmp/aiperf_mock_config_$(date +%s).yaml"
python3 - <<EOF
import yaml, sys

# Load the original config
with open("$CONFIG_FILE", "r") as f:
    config = yaml.safe_load(f)

# Update the config to use mock server
for client in config.get("workers", {}).get("clients", []):
    if client.get("client_type") == "openai":
        client["base_url"] = f"http://localhost:$MOCK_PORT/v1"
        client["api_key"] = "mock_api_key"
        if "auth" in client:
            client["auth"]["api_key"] = "mock_api_key"
        print(f"Updated OpenAI client config to use mock server at {client['base_url']}")

# Save the modified config
with open("$TEMP_CONFIG", "w") as f:
    yaml.dump(config, f)
    print(f"Saved modified config to {f.name}")
EOF

if [ ! -f "$TEMP_CONFIG" ]; then
  echo "Failed to create modified config"
  exit 1
fi

# Start the mock OpenAI server
echo "Starting mock OpenAI server on port $MOCK_PORT..."
python3 - <<EOF &
import os, sys
import uvicorn
from fastapi import FastAPI, Request, Response
import json
import random
import time
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mock_openai")

# Create FastAPI app
app = FastAPI(title="Mock OpenAI API")

# Mock server settings
SETTINGS = {
    "delay_min": $MOCK_DELAY_MIN,
    "delay_max": $MOCK_DELAY_MAX,
    "error_rate": $MOCK_ERROR_RATE,
    "models": ["gpt-3.5-turbo", "gpt-4"],
}

# Mock response templates
responses = {
    "text": "This is a mock response from the OpenAI API. This would normally be a response from a real model, but we're using a mock server for testing.",
    "error": {"error": {"message": "Mock error response", "type": "mock_error", "code": "mock_error_code"}},
}

@app.get("/v1/models")
async def list_models():
    await asyncio.sleep(random.uniform(0.05, 0.2))
    return {
        "object": "list",
        "data": [
            {"id": model, "object": "model", "created": int(time.time()), "owned_by": "mock-owner"} 
            for model in SETTINGS["models"]
        ]
    }

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    # Get request body
    body = await request.json()
    model = body.get("model", "gpt-3.5-turbo")
    messages = body.get("messages", [])
    stream = body.get("stream", False)
    
    # Log request
    logger.info(f"Mock chat completion: model={model}, messages={len(messages)}, stream={stream}")
    
    # Random delay to simulate processing
    delay = random.uniform(SETTINGS["delay_min"], SETTINGS["delay_max"])
    
    # Simulate error response
    if random.random() < SETTINGS["error_rate"]:
        await asyncio.sleep(delay * 0.2)  # Errors usually happen faster
        return Response(
            content=json.dumps(responses["error"]),
            status_code=500,
            media_type="application/json"
        )
    
    # Generate response content based on the last message
    response_content = responses["text"]
    if messages and "content" in messages[-1]:
        response_content += f" You asked: {messages[-1]['content'][:50]}..."
    
    # Handle streaming response
    if stream:
        async def generate_stream():
            # Initial chunk with role
            yield f"data: {json.dumps({'id': f'chatcmpl-{int(time.time())}', 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model, 'choices': [{'index': 0, 'delta': {'role': 'assistant'}, 'finish_reason': None}]})}\n\n"
            
            # Split response into words for streaming
            words = response_content.split()
            chunk_size = max(1, len(words) // 10)
            chunks = [' '.join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
            
            for i, chunk in enumerate(chunks):
                await asyncio.sleep(delay / len(chunks))
                finish_reason = "stop" if i == len(chunks) - 1 else None
                yield f"data: {json.dumps({'id': f'chatcmpl-{int(time.time())}', 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model, 'choices': [{'index': 0, 'delta': {'content': chunk}, 'finish_reason': finish_reason}]})}\n\n"
            
            # Final chunk
            yield f"data: [DONE]\n\n"
        
        return Response(
            content=generate_stream(),
            media_type="text/event-stream"
        )
    else:
        # Non-streaming response
        await asyncio.sleep(delay)
        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_content
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": sum(len(m.get("content", "")) // 4 for m in messages),
                "completion_tokens": len(response_content) // 4,
                "total_tokens": sum(len(m.get("content", "")) // 4 for m in messages) + len(response_content) // 4
            }
        }

@app.post("/v1/completions")
async def completions(request: Request):
    # Get request body
    body = await request.json()
    model = body.get("model", "text-davinci-003")
    prompt = body.get("prompt", "")
    stream = body.get("stream", False)
    
    # Log request
    logger.info(f"Mock completion: model={model}, prompt={prompt[:50]}..., stream={stream}")
    
    # Random delay to simulate processing
    delay = random.uniform(SETTINGS["delay_min"], SETTINGS["delay_max"])
    
    # Simulate error response
    if random.random() < SETTINGS["error_rate"]:
        await asyncio.sleep(delay * 0.2)  # Errors usually happen faster
        return Response(
            content=json.dumps(responses["error"]),
            status_code=500,
            media_type="application/json"
        )
    
    # Generate response content
    response_content = responses["text"]
    if prompt:
        response_content += f" You prompted: {prompt[:50]}..."
    
    # Handle streaming response
    if stream:
        async def generate_stream():
            # Split response into words for streaming
            words = response_content.split()
            chunk_size = max(1, len(words) // 10)
            chunks = [' '.join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
            
            for i, chunk in enumerate(chunks):
                await asyncio.sleep(delay / len(chunks))
                finish_reason = "stop" if i == len(chunks) - 1 else None
                yield f"data: {json.dumps({'id': f'cmpl-{int(time.time())}', 'object': 'text_completion', 'created': int(time.time()), 'model': model, 'choices': [{'text': chunk, 'index': 0, 'finish_reason': finish_reason}]})}\n\n"
            
            # Final chunk
            yield f"data: [DONE]\n\n"
        
        return Response(
            content=generate_stream(),
            media_type="text/event-stream"
        )
    else:
        # Non-streaming response
        await asyncio.sleep(delay)
        return {
            "id": f"cmpl-{int(time.time())}",
            "object": "text_completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "text": response_content,
                    "index": 0,
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": len(prompt) // 4,
                "completion_tokens": len(response_content) // 4,
                "total_tokens": len(prompt) // 4 + len(response_content) // 4
            }
        }

if __name__ == "__main__":
    print(f"Starting mock OpenAI server on port $MOCK_PORT")
    uvicorn.run(app, host="0.0.0.0", port=$MOCK_PORT, log_level="info")
EOF

MOCK_SERVER_PID=$!
echo "Mock OpenAI server started with PID: $MOCK_SERVER_PID"

# Wait for server to start
echo "Waiting for mock server to start..."
sleep 2

# Check if server is running
if ! ps -p $MOCK_SERVER_PID > /dev/null; then
  echo "Mock server failed to start"
  exit 1
fi

# Run AIPerf
echo "Starting AIPerf with duration $DURATION seconds..."
python3 -m aiperf.run --config $TEMP_CONFIG --duration $DURATION $VERBOSE

echo "AIPerf run completed" 
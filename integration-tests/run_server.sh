#!/bin/bash
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

# AI Performance Integration Test Server startup script

# Default configuration
export SERVER_PORT=${SERVER_PORT:-8000}
export SERVER_HOST=${SERVER_HOST:-"0.0.0.0"}
export TTFT_MS=${TTFT_MS:-20.0}
export ITL_MS=${ITL_MS:-5.0}

echo "Starting AI Performance Integration Test Server..."
echo "Configuration:"
echo "  Port: $SERVER_PORT"
echo "  Host: $SERVER_HOST"
echo "  Time to First Token: ${TTFT_MS}ms"
echo "  Inter-token Latency: ${ITL_MS}ms"
echo ""

# Activate virtual environment if it exists
if [ -f "../.venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source ../.venv/bin/activate
fi

# Start the server
integration-server \
    --port "$SERVER_PORT" \
    --host "$SERVER_HOST" \
    --time-to-first-token-ms "$TTFT_MS" \
    --inter-token-latency-ms "$ITL_MS" \
    --log-level ERROR

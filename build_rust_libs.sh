#!/bin/bash
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

# Build script for Rust libraries

set -e

echo "Building Rust libraries for aiperf..."

. .venv/bin/activate

# Build streaming library
echo "Building aiperf_streaming..."
cd lib/streaming
maturin develop --release
cd ../..

echo "✅ All Rust libraries built successfully!"
echo "You can now import:"
echo "  from aiperf_streaming import StreamingHttpClient, StreamingOptions, RequestTimers, RequestTimerKind"

<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# Installation and Build Instructions

This document provides detailed instructions for building and installing the `aiperf_streaming` library.

## 🛠️ Prerequisites

### System Requirements
- **Operating System**: Linux (x86_64, aarch64), macOS (x86_64, arm64), or Windows (x86_64)
- **Python**: 3.8 or higher
- **Rust**: 1.70 or higher
- **Memory**: At least 2GB RAM for compilation
- **Storage**: ~500MB for build artifacts

### Install Rust

If you don't have Rust installed:

```bash
# Install Rust using rustup
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Restart your shell or run:
source ~/.cargo/env

# Verify installation
rustc --version
cargo --version
```

### Install Python Dependencies

```bash
# Install maturin for building Python extensions
pip install maturin

# Install development dependencies (optional)
pip install pytest pydantic
```

## 🚀 Building from Source

### Option 1: Development Build (Recommended for Development)

```bash
# Clone the repository
git clone <repository-url>
cd aiperf_streaming

# Build in development mode (faster builds, debug symbols)
maturin develop

# Verify the installation
python -c "import aiperf_streaming; print('✅ Successfully imported aiperf_streaming')"
```

### Option 2: Release Build (Recommended for Production)

```bash
# Build with optimizations (slower build, faster runtime)
maturin develop --release

# Or build wheel for distribution
maturin build --release
```

### Option 3: Build and Install from Wheel

```bash
# Build a wheel
maturin build --release

# Install the built wheel
pip install target/wheels/aiperf_streaming-*.whl
```

## 🐍 Building for Specific Python Versions

### Build for Current Python Version

```bash
maturin develop
```

### Build for Specific Python Version

```bash
# For Python 3.9
maturin develop --python python3.9

# For Python 3.10
maturin develop --python python3.10

# For Python 3.11
maturin develop --python python3.11
```

### Build Universal Wheels

```bash
# Build wheels for multiple Python versions
maturin build --release --universal2  # macOS universal binary
maturin build --release --target x86_64-pc-windows-msvc  # Windows
maturin build --release --target x86_64-unknown-linux-gnu  # Linux
```

## 🔧 Advanced Build Configuration

### Rust Features

The library supports several Rust features:

```bash
# Build with all features
maturin develop --release --features "full"

# Build with specific features
maturin develop --release --features "rustls-tls"
```

### Environment Variables

Set these environment variables to customize the build:

```bash
# Optimize for current CPU architecture
export RUSTFLAGS="-C target-cpu=native"

# Use more parallel jobs for compilation
export CARGO_BUILD_JOBS=8

# Build with link-time optimization
export CARGO_BUILD_RUSTFLAGS="-C lto=fat"

# Then build
maturin develop --release
```

### Cross-Compilation

For cross-compilation to different architectures:

```bash
# Install cross-compilation targets
rustup target add aarch64-unknown-linux-gnu
rustup target add x86_64-pc-windows-msvc

# Cross-compile for ARM64 Linux
maturin build --release --target aarch64-unknown-linux-gnu

# Cross-compile for Windows
maturin build --release --target x86_64-pc-windows-msvc
```

## 🧪 Testing the Build

### Run Basic Tests

```bash
# Run the Python test suite
pytest tests/

# Run with verbose output
pytest -v tests/

# Run with coverage
pytest --cov=aiperf_streaming tests/
```

### Run Examples

```bash
# Run basic usage example
python examples/basic_usage.py

# Run AI inference timing example
python examples/ai_inference_timing.py
```

### Manual Testing

```python
# Test basic functionality
python -c "
from aiperf_streaming import StreamingHttpClient, StreamingRequest, PrecisionTimer
timer = PrecisionTimer()
print(f'Timer working: {timer.now_ns()}')
client = StreamingHttpClient()
print('✅ All components imported successfully')
"
```

## 🐳 Docker Build (Optional)

For consistent builds across environments:

```dockerfile
# Dockerfile.build
FROM rust:1.70 AS builder

WORKDIR /app
COPY . .

# Install Python and maturin
RUN apt-get update && apt-get install -y python3 python3-pip
RUN pip3 install maturin

# Build the wheel
RUN maturin build --release --out dist

# Runtime image
FROM python:3.11-slim
COPY --from=builder /app/dist/*.whl /tmp/
RUN pip install /tmp/*.whl

# Test the installation
RUN python -c "import aiperf_streaming; print('✅ Docker build successful')"
```

Build with Docker:

```bash
# Build the Docker image
docker build -f Dockerfile.build -t aiperf_streaming:build .

# Extract the wheel
docker run --rm -v $(pwd)/dist:/output aiperf_streaming:build \
    sh -c "cp /app/dist/*.whl /output/"

# Install the wheel
pip install dist/*.whl
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Rust Compilation Errors

```bash
# Update Rust to latest version
rustup update

# Clear cargo cache
cargo clean

# Retry build
maturin develop --release
```

#### 2. Python Import Errors

```bash
# Check if the module was installed correctly
python -c "import aiperf_streaming"

# If import fails, check the installation path
python -c "import sys; print(sys.path)"

# Reinstall if necessary
pip uninstall aiperf_streaming
maturin develop --release
```

#### 3. Performance Issues

```bash
# Ensure you're using release mode
maturin develop --release

# Check CPU optimizations
export RUSTFLAGS="-C target-cpu=native"
maturin develop --release
```

#### 4. Memory Issues During Build

```bash
# Reduce parallel compilation jobs
export CARGO_BUILD_JOBS=2
maturin develop --release

# Or use single-threaded compilation
export CARGO_BUILD_JOBS=1
maturin develop --release
```

### Platform-Specific Issues

#### Linux

```bash
# Install build dependencies
sudo apt-get update
sudo apt-get install build-essential libssl-dev pkg-config

# For older distributions, you might need:
sudo apt-get install python3-dev
```

#### macOS

```bash
# Install Xcode command line tools
xcode-select --install

# If using Homebrew:
brew install python@3.11
```

#### Windows

```bash
# Use Visual Studio Build Tools 2019 or newer
# Or install via chocolatey:
choco install visualstudio2019buildtools

# Set environment variable
set RUSTFLAGS=-C target-feature=+crt-static
```

### Getting Help

If you encounter issues:

1. **Check the logs**: Build errors are usually detailed in the output
2. **Search issues**: Check the GitHub issues for similar problems
3. **Minimal reproduction**: Try building on a clean environment
4. **Report bugs**: Create an issue with full build logs and system info

```bash
# Gather system information for bug reports
echo "System: $(uname -a)"
echo "Python: $(python --version)"
echo "Rust: $(rustc --version)"
echo "Cargo: $(cargo --version)"
echo "Maturin: $(maturin --version)"
```

## 📦 Distribution

### Creating Release Artifacts

```bash
# Build wheels for multiple platforms
maturin build --release --universal2

# Upload to PyPI (maintainers only)
maturin publish --username __token__ --password $PYPI_TOKEN
```

### Local Distribution

```bash
# Create source distribution
python setup.py sdist

# Create wheel
maturin build --release

# Install from local wheel
pip install dist/aiperf_streaming-*.whl
```

## ✅ Verification

After successful installation, verify everything works:

```python
#!/usr/bin/env python3
"""Verification script for aiperf_streaming installation."""

def verify_installation():
    try:
        # Test imports
        from aiperf_streaming import (
            StreamingHttpClient,
            StreamingRequest,
            PrecisionTimer,
            StreamingStats,
        )
        print("✅ All imports successful")

        # Test basic functionality
        timer = PrecisionTimer()
        timestamp = timer.now_ns()
        assert isinstance(timestamp, int)
        assert timestamp > 0
        print("✅ Timer functionality verified")

        # Test client creation
        client = StreamingHttpClient(timeout_ms=5000)
        stats = client.get_stats()
        assert isinstance(stats, dict)
        print("✅ Client creation verified")

        # Test request creation
        request = StreamingRequest(
            url="https://httpbin.org/get",
            method="GET"
        )
        assert request.url == "https://httpbin.org/get"
        assert request.method == "GET"
        print("✅ Request creation verified")

        print("\n🎉 Installation verification successful!")
        print("Your aiperf_streaming library is ready to use.")

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please check your installation.")
        return False
    except Exception as e:
        print(f"❌ Verification error: {e}")
        return False

    return True

if __name__ == "__main__":
    verify_installation()
```

Save this as `verify_install.py` and run:

```bash
python verify_install.py
```
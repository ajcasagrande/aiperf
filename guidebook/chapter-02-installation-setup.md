# Chapter 2: Installation and Setup

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Table of Contents
- [System Requirements](#system-requirements)
- [Python Version Requirements](#python-version-requirements)
- [Installation Methods](#installation-methods)
- [Virtual Environment Setup](#virtual-environment-setup)
- [Dependency Management](#dependency-management)
- [Verification Procedures](#verification-procedures)
- [Common Installation Issues](#common-installation-issues)
- [Configuration Files](#configuration-files)
- [Environment Variables](#environment-variables)
- [Key Takeaways](#key-takeaways)

## System Requirements

### Operating System
AIPerf is developed and tested on Linux systems, with support for:
- **Ubuntu 20.04, 22.04, 24.04** (Primary development platform)
- **CentOS/RHEL 8+**
- **Debian 11+**
- **Arch Linux** (As indicated by the OS version in the project)

While AIPerf may work on macOS and Windows, these platforms are not officially supported. Some known issues:
- macOS: Dashboard UI may cause corrupted ANSI sequences in certain terminal environments
- Windows: ZeroMQ and multiprocessing behavior may differ

**Recommendation**: Use Linux for production benchmarking and development.

### Hardware Requirements

#### Minimum Requirements
- **CPU**: 2 cores (x86-64 or ARM64)
- **RAM**: 4 GB
- **Disk**: 500 MB for installation, additional space for logs and results
- **Network**: Network connectivity to target inference endpoint

#### Recommended Requirements
For optimal performance and realistic benchmarking:
- **CPU**: 8+ cores (more cores enable more worker processes)
- **RAM**: 16 GB or more (especially for high concurrency)
- **Disk**: SSD with 10+ GB free space
- **Network**: Low-latency connection to target endpoint (same datacenter/region)

#### Special Considerations

**For High Concurrency Testing** (1000+ concurrent requests):
- 16+ CPU cores
- 32+ GB RAM
- Consider increasing system limits (see Common Installation Issues)

**For Production Use**:
- Dedicated benchmarking machine to avoid measurement interference
- Consistent hardware to ensure reproducible results
- Monitor system resources to ensure they're not the bottleneck

### Network Requirements
- HTTP/HTTPS connectivity to target inference endpoints
- Sufficient bandwidth (typically not a bottleneck for LLM inference)
- Low and stable latency (for accurate measurements)
- Firewall rules allowing outbound connections

### GPU Requirements
AIPerf itself does not require GPUs - it's a client-side benchmarking tool. However:
- The inference endpoint you're testing will typically need GPUs
- For development/testing, you might run a local inference server that requires GPUs
- GPU telemetry features (coming soon) will connect to GPU metrics endpoints

## Python Version Requirements

### Supported Python Versions
AIPerf requires **Python 3.10 or higher**. This is specified in the project configuration:

```toml
# From /home/anthony/nvidia/projects/aiperf/pyproject.toml
requires-python = ">=3.10"
```

### Recommended Version
**Python 3.10** is the primary development and testing version. Python 3.11 and 3.12 should also work but may have less testing coverage.

### Why Python 3.10+?
The Python 3.10+ requirement is driven by:
1. **Type Hinting Features**: Improved type hints like `X | Y` union syntax
2. **Pattern Matching**: Structural pattern matching (match/case statements)
3. **Pydantic v2**: Requires Python 3.8+ but works best with 3.10+
4. **asyncio Improvements**: Better async context management and performance
5. **Security**: Python 3.9 and earlier are approaching or past end-of-life

### Checking Your Python Version

```bash
python3 --version
# Should show Python 3.10.x or higher
```

If you have multiple Python versions:
```bash
python3.10 --version
python3.11 --version
```

## Installation Methods

AIPerf can be installed via pip from PyPI or from source. Each method has its use cases.

### Method 1: Install from PyPI (Recommended for Users)

This is the simplest method for users who want to use AIPerf without modifying it.

```bash
# Install the latest stable version
pip install aiperf

# Or install a specific version
pip install aiperf==0.1.1

# Verify installation
aiperf --help
```

**Advantages**:
- Quick and simple
- Gets stable, tested releases
- Automatic dependency management
- Easy to update

**When to use**:
- Running benchmarks
- Production use
- CI/CD integration
- When you don't need to modify AIPerf code

### Method 2: Install from Source (Recommended for Developers)

Install from the GitHub repository for the latest features or development work.

```bash
# Clone the repository
git clone https://github.com/ai-dynamo/aiperf.git
cd aiperf

# Install in editable mode
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"

# Verify installation
aiperf --version
```

**Advantages**:
- Access to latest features
- Ability to modify code
- Easier to contribute back
- See changes immediately (editable install)

**When to use**:
- Contributing to AIPerf
- Testing unreleased features
- Custom modifications
- Development and debugging

### Method 3: Install from Specific Branch/Tag

For testing specific versions or branches:

```bash
# Install from a specific branch
pip install git+https://github.com/ai-dynamo/aiperf.git@main

# Install from a specific tag
pip install git+https://github.com/ai-dynamo/aiperf.git@v0.1.1

# Install from a specific commit
pip install git+https://github.com/ai-dynamo/aiperf.git@85bd080
```

### Method 4: Using Docker

While not officially documented, you can use Docker for isolated environments:

```bash
# Example Dockerfile
FROM ubuntu:24.04

RUN apt update && apt install -y python3.10 python3-pip git
RUN pip install aiperf

ENTRYPOINT ["aiperf"]
```

Build and use:
```bash
docker build -t aiperf:latest .
docker run --rm aiperf:latest --help
```

## Virtual Environment Setup

Using a virtual environment is **strongly recommended** to avoid dependency conflicts with system packages or other Python projects.

### Using venv (Standard Library)

```bash
# Create a virtual environment
python3 -m venv aiperf-env

# Activate the environment
source aiperf-env/bin/activate  # Linux/macOS
# or
aiperf-env\Scripts\activate     # Windows

# Install AIPerf
pip install aiperf

# Verify you're in the virtual environment
which python  # Should show path to aiperf-env
python --version

# When done, deactivate
deactivate
```

### Using virtualenv

```bash
# Install virtualenv if needed
pip install virtualenv

# Create virtual environment
virtualenv aiperf-env

# Activate and use
source aiperf-env/bin/activate
pip install aiperf
```

### Using conda

```bash
# Create conda environment
conda create -n aiperf python=3.10

# Activate environment
conda activate aiperf

# Install AIPerf
pip install aiperf

# Deactivate
conda deactivate
```

### Using uv (Modern, Fast Alternative)

The AIPerf documentation examples use `uv` for fast dependency management:

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# Create virtual environment
uv venv --python 3.10

# Activate
source .venv/bin/activate

# Install AIPerf
uv pip install aiperf

# Or install from source
git clone https://github.com/ai-dynamo/aiperf.git
uv pip install ./aiperf
```

**Why uv?**
- 10-100x faster than pip
- Better dependency resolution
- Compatible with pip
- Modern tooling

### Best Practices

1. **One Environment Per Project**: Keep AIPerf in its own environment
2. **Document Requirements**: Save dependencies with `pip freeze > requirements.txt`
3. **Activate Before Use**: Always activate the environment before running aiperf
4. **Consistent Python Version**: Use the same Python version across environments

## Dependency Management

### Core Dependencies

AIPerf has a carefully curated set of dependencies (from `/home/anthony/nvidia/projects/aiperf/pyproject.toml`):

```toml
dependencies = [
  "aiofiles~=24.1.0",          # Async file I/O
  "aiohttp~=3.12.14",          # Async HTTP client
  "cyclopts>=3,<4",            # CLI parsing
  "numpy~=2.2.6",              # Numerical operations
  "openai[aiohttp]~=1.92.2",   # OpenAI client library
  "orjson~=3.10.18",           # Fast JSON parsing
  "pandas~=2.3.0",             # Data analysis
  "pillow~=11.1.0",            # Image processing
  "psutil~=7.0.0",             # System monitoring
  "pydantic~=2.11.4",          # Data validation
  "pydantic-settings~=2.10.0", # Settings management
  "pyzmq~=26.4.0",             # ZeroMQ bindings
  "rich~=14.1.0",              # Terminal formatting
  "ruamel.yaml~=0.18.12",      # YAML parsing
  "setproctitle~=1.3.6",       # Process naming
  "soundfile~=0.13.1",         # Audio file support
  "textual~=5.3.0",            # TUI framework
  "tqdm>=4.67.1",              # Progress bars
  "transformers>=4.52.0",      # HuggingFace tokenizers
  "uvloop~=0.21.0",            # Fast asyncio event loop
]
```

### Development Dependencies

For development work, install the dev dependencies:

```bash
pip install -e ".[dev]"
```

Development dependencies include:
```toml
dev = [
  "black>=25.1.0",          # Code formatting
  "mkinit>=1.1.0",          # Init file generation
  "pre-commit>=4.2.0",      # Git hooks
  "pytest-asyncio",         # Async test support
  "pytest-cov",             # Coverage reporting
  "pytest>=7.0.0",          # Testing framework
  "pytest-xdist>=3.8.0",    # Parallel testing
  "ruff>=0.0.0",            # Fast linting
  "scipy>=1.13.0",          # Scientific computing
]
```

### Managing Dependencies

#### View Installed Dependencies
```bash
pip list
pip show aiperf
```

#### Update Dependencies
```bash
# Update AIPerf
pip install --upgrade aiperf

# Update all packages (be careful!)
pip list --outdated
pip install --upgrade package-name
```

#### Lock Dependencies
For reproducible environments:
```bash
# Generate requirements file
pip freeze > requirements.txt

# Install from requirements file
pip install -r requirements.txt
```

#### Check for Conflicts
```bash
pip check
```

### Handling Dependency Issues

If you encounter dependency conflicts:

1. **Start Fresh**: Create a new virtual environment
2. **Update pip**: `pip install --upgrade pip`
3. **Install One at a Time**: Install dependencies individually to identify conflicts
4. **Check Compatibility**: Verify Python version compatibility
5. **Consult Documentation**: Check if specific versions are required

## Verification Procedures

After installation, verify that AIPerf is working correctly.

### Basic Verification

```bash
# Check that aiperf is in your PATH
which aiperf
# Should output: /path/to/aiperf-env/bin/aiperf

# Check version
aiperf --version
# Should output: aiperf, version 0.1.1 (or your installed version)

# Check help
aiperf --help
# Should display help text

# Check profile command help
aiperf profile --help
# Should display profile command options
```

### Python Import Test

```bash
python -c "import aiperf; print(aiperf.__version__)"
# Should print version without errors
```

### Dependency Check

```bash
# Verify key dependencies are installed
python -c "import aiohttp, zmq, pydantic, pandas, rich; print('All imports successful')"
```

### Full Functionality Test

Run a minimal benchmark against a test endpoint (requires a running inference server):

```bash
# Example with a local vLLM server running on port 8000
aiperf profile \
    --model test-model \
    --url localhost:8000 \
    --endpoint-type chat \
    --request-count 5 \
    --concurrency 1

# If successful, you should see:
# - Progress output
# - Metric tables
# - No errors
```

### Verification Checklist

- [ ] `aiperf --version` works
- [ ] `aiperf --help` shows options
- [ ] Python imports work
- [ ] No dependency conflicts (`pip check`)
- [ ] Can run a simple profile command
- [ ] Results are written to artifacts directory
- [ ] Log files are created

## Common Installation Issues

### Issue 1: Python Version Mismatch

**Symptom**:
```
ERROR: Package 'aiperf' requires a different Python: 3.9.x not in '>=3.10'
```

**Solution**:
```bash
# Install Python 3.10 or higher
# On Ubuntu:
sudo apt update
sudo apt install python3.10 python3.10-venv

# Use specific Python version
python3.10 -m venv aiperf-env
source aiperf-env/bin/activate
pip install aiperf
```

### Issue 2: Permission Errors

**Symptom**:
```
ERROR: Could not install packages due to an OSError: [Errno 13] Permission denied
```

**Solution**:
```bash
# Don't use sudo with pip!
# Instead, use a virtual environment or user install:
pip install --user aiperf

# Better: use a virtual environment (recommended)
python3 -m venv aiperf-env
source aiperf-env/bin/activate
pip install aiperf
```

### Issue 3: ZeroMQ Build Failures

**Symptom**:
```
error: command 'gcc' failed with exit status 1
```

**Solution**:
```bash
# Install system dependencies
# On Ubuntu/Debian:
sudo apt install build-essential python3-dev libzmq3-dev

# On RHEL/CentOS:
sudo yum install gcc gcc-c++ python3-devel zeromq-devel

# Then retry installation
pip install aiperf
```

### Issue 4: Port Exhaustion at High Concurrency

**Symptom**:
```
ConnectionError: Cannot assign requested address
```

**Solution**:
```bash
# Increase system limits
# Temporarily:
sudo sysctl -w net.ipv4.ip_local_port_range="1024 65535"
sudo sysctl -w net.ipv4.tcp_fin_timeout=30
sudo sysctl -w net.core.somaxconn=4096

# Permanently: Add to /etc/sysctl.conf:
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_fin_timeout = 30
net.core.somaxconn = 4096

# Apply changes
sudo sysctl -p

# Also increase file descriptor limits
ulimit -n 65535

# Make permanent by adding to /etc/security/limits.conf:
* soft nofile 65535
* hard nofile 65535
```

### Issue 5: AIPerf Hangs on Startup

**Symptom**: AIPerf appears to freeze during initialization

**Solution**:
1. Check configuration for invalid settings
2. Enable debug logging: Set environment variable `AIPERF_LOG_LEVEL=DEBUG`
3. Check if the endpoint is reachable
4. Verify ZeroMQ ports are available
5. Look for errors in log files in `artifacts/logs/`

### Issue 6: Import Errors

**Symptom**:
```
ModuleNotFoundError: No module named 'aiperf'
```

**Solution**:
```bash
# Ensure virtual environment is activated
source aiperf-env/bin/activate

# Verify installation
pip show aiperf

# If not installed, install it
pip install aiperf

# For editable installs, ensure you're in the right directory
cd /path/to/aiperf
pip install -e .
```

### Issue 7: Terminal UI Corruption on macOS

**Symptom**: Terminal becomes unusable after running AIPerf with dashboard UI

**Solution**:
```bash
# Reset terminal
reset

# Use simple UI instead
aiperf profile --ui simple [other options...]

# Or disable UI completely
aiperf profile --ui none [other options...]
```

### Issue 8: SSL Certificate Errors

**Symptom**:
```
SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**Solution**:
```bash
# Update certificates
# On Ubuntu:
sudo apt update
sudo apt install ca-certificates
sudo update-ca-certificates

# On macOS:
# Run the certificate installer in Python installation directory
/Applications/Python\ 3.10/Install\ Certificates.command

# As last resort (not recommended for production):
# Disable SSL verification (use with caution!)
export AIOHTTP_NO_VERIFY_SSL=1
```

## Configuration Files

AIPerf uses multiple configuration mechanisms.

### User Configuration
All CLI arguments constitute user configuration, which is captured in:
- **UserConfig** object (in-memory)
- **CLI command** string (saved in results)
- **inputs.json** file (artifact)

No separate user config file is required - everything is specified via CLI arguments.

### Service Configuration
Service-level configuration can be provided via:

1. **Environment Variables**
2. **Configuration File**: `/path/to/service_config.yaml`
3. **Programmatic Configuration**: When embedding AIPerf

Example service configuration:
```yaml
# service_config.yaml
workers:
  min: 4
  max: 16

record_processor_service_count: 4

ui_type: dashboard

service_run_type: multiprocess

log_level: INFO
```

Load custom service config:
```bash
# Service config is loaded automatically from environment
# or can be programmatically specified
export AIPERF_SERVICE_CONFIG=/path/to/service_config.yaml
aiperf profile [options...]
```

### Artifact Configuration
AIPerf creates an `artifacts/` directory containing:
- **logs/**: Log files
- **results/**: Benchmark results (CSV, JSON)
- **inputs.json**: Captured input payloads
- **profile_export.json**: Complete results export

Location can be customized:
```bash
aiperf profile --output-dir /custom/path [options...]
```

## Environment Variables

AIPerf respects several environment variables:

### Logging Configuration
```bash
# Set log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
export AIPERF_LOG_LEVEL=DEBUG

# Enable developer mode (more verbose output)
export AIPERF_DEV_MODE=1
```

### HTTP Configuration
```bash
# Set HTTP connection limit per worker
export AIPERF_HTTP_CONNECTION_LIMIT=100

# Disable SSL verification (not recommended)
export AIOHTTP_NO_VERIFY_SSL=1
```

### ZeroMQ Configuration
```bash
# Set ZeroMQ I/O threads
export ZMQ_IO_THREADS=4
```

### System Configuration
```bash
# Force specific number of workers
export AIPERF_MAX_WORKERS=8

# Set service configuration file
export AIPERF_SERVICE_CONFIG=/path/to/service_config.yaml
```

### Example Environment Setup

```bash
# .env file for AIPerf
export AIPERF_LOG_LEVEL=INFO
export AIPERF_HTTP_CONNECTION_LIMIT=100
export AIPERF_MAX_WORKERS=8

# Load environment
source .env

# Run AIPerf
aiperf profile [options...]
```

## Key Takeaways

1. **Python 3.10+ Required**: AIPerf needs Python 3.10 or higher for modern language features and dependencies.

2. **Virtual Environments Are Essential**: Always use virtual environments to avoid dependency conflicts and ensure reproducible installations.

3. **Multiple Installation Methods**: Choose PyPI for stability, source for development, or Docker for isolation.

4. **Dependencies Are Well-Managed**: AIPerf has pinned versions for stability, but be aware of the dependency tree for troubleshooting.

5. **Verify Your Installation**: Run basic tests to ensure everything is working before starting benchmarks.

6. **System Limits Matter**: For high-concurrency testing, you'll need to adjust system limits (file descriptors, ports, etc.).

7. **Configuration Is Flexible**: Use CLI arguments for user config, environment variables for service config, and files for complex setups.

8. **Common Issues Are Documented**: Most installation problems have known solutions - consult this chapter and the issue tracker.

9. **Linux Is Recommended**: While AIPerf may work on other platforms, Linux provides the best experience and support.

10. **Keep It Updated**: Stay on recent AIPerf versions for bug fixes and new features, but test updates in non-production environments first.

With AIPerf properly installed and verified, you're ready to run your first benchmarks. The next chapter provides a quick start guide to get you benchmarking immediately.

---

Next: [Chapter 3: Quick Start Guide](chapter-03-quick-start.md)

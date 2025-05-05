# AIPerf Debug Mode Improvements

This document describes the improvements made to AIPerf's debug mode to handle worker initialization with placeholder API keys and 404 errors from mock servers.

## Overview

The AIPerf system has been enhanced to properly handle the following scenarios in debug mode:

1. Worker initialization with placeholder API keys
2. Mock server 404 errors for API endpoints
3. Automatic fallback to mock responses in debug mode

These improvements ensure that the system can be tested without requiring real API keys, and that it gracefully handles errors from mock servers.

## Key Improvements

### 1. Enhanced OpenAIClient

- Added robust handling of placeholder API keys in debug mode
- Improved error handling for HTTP errors, including 404 Not Found responses
- Added automatic fallback to mock responses when encountering errors in debug mode
- Enhanced session management to prevent resource leaks

### 2. Improved ConcreteWorker

- Added better metadata handling for debug mode configuration
- Enhanced error logging with full stack traces
- Improved error handling during client initialization

### 3. Testing Tools

- Added a mock server implementation that simulates 404 errors for API endpoints
- Created comprehensive test scripts to verify debug mode functionality
- Added tests for both direct client usage and worker-mediated usage

## How to Test

### Basic Test

Run the basic test script to verify that worker initialization works with placeholder API keys:

```bash
python test_worker.py
```

This will test the OpenAIClient and ConcreteWorker with placeholder API keys in debug mode, without requiring a mock server.

### Testing with Mock Server

To test the full functionality with a mock server that returns 404 errors:

1. Start the mock server in one terminal:

```bash
python mock_server.py
```

2. Run the mock server test script in another terminal:

```bash
python test_with_mock_server.py
```

This will test the OpenAIClient and ConcreteWorker against the mock server, verifying that they correctly handle 404 errors and fall back to mock responses.

## Debug Mode Configuration

To enable debug mode in your AIPerf configuration, set the `debug_mode` flag in the endpoint metadata:

```yaml
endpoints:
  - name: my_endpoint
    url: https://api.openai.com/v1
    api_type: openai
    headers:
      Content-Type: application/json
    auth:
      api_key: YOUR_API_KEY  # Can be a placeholder in debug mode
    timeout: 30.0
    metadata:
      debug_mode: true  # Enable debug mode
```

When debug mode is enabled, the system will:

1. Allow initialization with placeholder API keys
2. Return mock responses instead of making real API calls
3. Automatically fall back to mock responses when encountering errors

## Troubleshooting

If you encounter issues with the mock server or debug mode:

1. Ensure that the mock server is running on the expected host and port
2. Verify that debug_mode is set to true in your endpoint configuration
3. Check the logs for detailed error messages
4. Ensure that the client is properly cleaned up after use to prevent resource leaks

## Implementation Details

The key implementation improvements are in:

- `aiperf/api/openai_client.py`: Enhanced to handle 404 errors and debug mode
- `aiperf/workers/concrete_worker.py`: Improved metadata handling and error reporting
- `test_worker.py`: Basic test script for debug mode
- `mock_server.py`: Mock server implementation that returns 404 errors
- `test_with_mock_server.py`: Comprehensive test script for mock server integration 
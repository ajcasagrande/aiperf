# AIPerf Mock OpenAI Server

This package provides a mock implementation of the OpenAI API for testing AIPerf without using actual OpenAI API credits.

## Overview

The AIPerf benchmarking system requires connecting to an LLM API service like OpenAI. This mock server allows you to:

1. Run AIPerf tests without using real OpenAI API credits
2. Test the benchmarking system's functionality in a controlled environment 
3. Develop and debug AIPerf without internet connectivity

## Components

This package includes several components:

1. **Mock OpenAI Server**: A FastAPI-based server that mimics the OpenAI API endpoints
2. **Config Modifier**: A utility to update AIPerf configs to use the mock server
3. **AIPerf Patches**: Scripts to fix communication issues in AIPerf when using the mock server

## Installation

No additional installation is needed as long as you have the AIPerf system installed. To install the mock server dependencies:

```bash
python -m pip install -r requirements-mock.txt
```

## Usage

### Option 1: Using the Simple Run Script

The easiest way to run the mock server is with the provided script:

```bash
./run_mock_server.sh
```

This will:
1. Install required dependencies
2. Create a modified configuration that points to the mock server
3. Start the mock OpenAI API server on port 8000

### Option 2: Step-by-Step Setup

#### 1. Start the Mock Server

```bash
python mock_openai_server.py
```

The server will start on `http://localhost:8000`.

#### 2. Modify AIPerf Config

```bash
python modify_config.py aiperf/config/examples/openai_example.yaml
```

This will create a modified config file that points to the mock server.

#### 3. Run AIPerf with the Mock Server

```bash
python -m aiperf_mock_patch --config aiperf/config/examples/openai_example_mock.yaml
```

The `aiperf_mock_patch.py` script applies runtime patches to improve compatibility with the mock server.

### Option 3: Fix AIPerf Component Registration Issues

If you're experiencing communication issues between AIPerf components:

```bash
./fix_component_registration.py
```

This will fix issues with component registration and communication in AIPerf.

## Features of the Mock Server

### API Endpoints

The mock server implements these OpenAI API endpoints:

- `GET /v1/models` - List available models
- `POST /v1/chat/completions` - Chat completions API
- `POST /v1/completions` - Text completions API

### Advanced Controls

The mock server provides additional endpoints for testing and control:

- `GET /mock/settings` - View current server settings
- `POST /mock/settings` - Update server settings
- `GET /mock/requests` - View request log
- `POST /mock/clear` - Clear request log

### Customizing Server Behavior

To modify the server's behavior:

```bash
curl -X POST http://localhost:8000/mock/settings -H "Content-Type: application/json" \
  -d '{"delay_min": 0.2, "delay_max": 1.5, "error_rate": 0.05, "token_rate": 20.0}'
```

Settings include:
- `delay_min`: Minimum response delay (seconds)
- `delay_max`: Maximum response delay (seconds)
- `error_rate`: Probability of returning an error (0.0-1.0)
- `token_rate`: Tokens per second for streaming responses

## Troubleshooting

### Common Issues

1. **Component communication errors**:
   - Run `./fix_component_registration.py` to fix these issues

2. **Timing credit synchronization issues**:
   - Use the `aiperf_mock_patch.py` script to run AIPerf

3. **"Target component not found" errors**:
   - These are expected when running with the mock server and will be handled automatically

## Advanced Usage

### Custom Mock Responses

You can modify the responses in `mock_openai_server.py` to suit your testing needs:

```python
# Find the MOCK_RESPONSES dictionary
MOCK_RESPONSES = {
    "chat": [
        "Your custom response here",
        # Add more responses
    ],
    # ...
}
```

### Testing With Error Conditions

To test AIPerf's error handling, increase the error rate:

```bash
curl -X POST http://localhost:8000/mock/settings -H "Content-Type: application/json" \
  -d '{"error_rate": 0.3}'
```

This will cause 30% of requests to return errors.

## Architecture

The system consists of:

1. **Mock OpenAI Server**: Simulates the OpenAI API
2. **Config Modifier**: Updates AIPerf config files to point to the mock server
3. **Patch Scripts**: Apply fixes to AIPerf at runtime to handle edge cases

## Limitations

This mock server has several limitations:

- Responses are pre-defined, not dynamically generated
- Limited to a fixed set of models
- Simplified token counting
- No support for advanced features like function calling, tools, etc.

## License

This mock server is provided under the same license as the AIPerf project. 
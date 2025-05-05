# Mock OpenAI API Server

This is a mock server that simulates the OpenAI API for testing the AIPerf benchmarking system locally without using actual OpenAI API credits.

## Features

- Simulates the main OpenAI API endpoints:
  - `/v1/models`
  - `/v1/chat/completions`
  - `/v1/completions`
- Supports both streaming and non-streaming responses
- Configurable response delays and error rates
- Request logging for debugging
- Authentication simulation (accepts any token except "invalid_token")

## Installation

1. Install the required dependencies:

```bash
pip install -r requirements-mock.txt
```

## Usage

1. Start the mock server:

```bash
python mock_openai_server.py
```

This will start the server on `http://localhost:8000`.

2. Configure AIPerf to use the mock server by editing the OpenAI configuration in your config file:

```yaml
ai_client:
  type: "openai"
  config:
    api_key: "sk-mock-key" # Can be any value except "invalid_token"
    base_url: "http://localhost:8000"
    # Other OpenAI configuration...
```

3. Run your AIPerf tests as usual - they will now use the mock server instead of the real OpenAI API.

## Server Control Endpoints

The mock server provides additional endpoints for control and monitoring:

- `GET /mock/settings` - Get current server settings
- `POST /mock/settings` - Update server settings
- `GET /mock/requests` - View request log
- `POST /mock/clear` - Clear request log

### Adjusting Server Behavior

You can customize the server behavior by updating settings:

```bash
curl -X POST http://localhost:8000/mock/settings -H "Content-Type: application/json" \
  -d '{"delay_min": 0.5, "delay_max": 2.0, "error_rate": 0.1, "token_rate": 10.0}'
```

Settings include:
- `delay_min`: Minimum response delay in seconds
- `delay_max`: Maximum response delay in seconds
- `error_rate`: Probability of returning an error (0.0-1.0)
- `token_rate`: Tokens per second for streaming responses

## Viewing Request History

To see all requests received by the server:

```bash
curl http://localhost:8000/mock/requests
```

## Testing with the API

The mock server implements the same API as OpenAI, so you can use the OpenAI client libraries:

```python
import openai

client = openai.OpenAI(
    api_key="sk-mock-key",
    base_url="http://localhost:8000"
)

response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello, how are you?"}]
)

print(response.choices[0].message.content)
``` 
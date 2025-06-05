<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# Backend Client Factory Pattern

**Summary:** AIPerf uses a sophisticated factory pattern to manage multiple backend client types (OpenAI, gRPC, HTTP, DynamoDB), providing a unified interface for external service integrations with automatic registration and type-safe configuration.

## Overview

The Backend Client Factory pattern in AIPerf provides a centralized mechanism for creating and managing different types of backend clients. This pattern enables seamless integration with various external services like OpenAI APIs, gRPC services, HTTP endpoints, and DynamoDB databases. The factory uses a registration-based approach where backend client types are automatically registered using decorators, ensuring type safety and configuration validation through Pydantic models.

## Key Concepts

- **Factory Registration**: Automatic client type registration using decorators
- **Type-Safe Configuration**: Generic Pydantic models for client-specific configuration
- **Protocol-Based Interface**: Consistent interface across all backend client types
- **Mixin Composition**: Shared functionality through configuration mixins
- **Runtime Client Creation**: Dynamic client instantiation based on configuration
- **Error Handling**: Comprehensive error handling for client creation and operation

## Practical Example

```python
# Backend Client Factory with automatic registration
from aiperf.backend.client_factory import BackendClientFactory
from aiperf.common.interfaces import BackendClientProtocol
from aiperf.common.models import BackendClientConfig

# Automatic registration using decorator
@BackendClientFactory.register(BackendClientType.OPENAI)
class OpenAIBackendClient(OpenAIClientMixin, OpenAIBackendClientProtocol):
    """OpenAI backend client with streaming support."""

    def __init__(self, cfg: BackendClientConfig[OpenAIBackendClientConfig]):
        super().__init__(cfg)
        # Initialize OpenAI client based on API type
        if self.client_config.api_type == OpenAIAPIType.AZURE:
            self._client = AsyncAzureOpenAI(
                api_key=self.client_config.api_key,
                base_url=self._build_base_url(),
                timeout=self.client_config.timeout_ms
            )
        else:
            self._client = AsyncOpenAI(
                api_key=self.client_config.api_key,
                base_url=self._build_base_url()
            )

    async def format_payload(self, endpoint: str, payload: Any) -> OpenAIRequest:
        """Format request payload for OpenAI API."""
        if endpoint == "v1/chat/completions":
            return OpenAIChatCompletionRequest(
                messages=payload["messages"],
                model=self.client_config.model,
                max_tokens=self.client_config.max_tokens,
                temperature=self.client_config.temperature,
                stream=True  # Enable streaming for performance measurement
            )
        raise ValueError(f"Unsupported endpoint: {endpoint}")

    async def send_request(self, endpoint: str, payload: OpenAIRequest) -> RequestRecord:
        """Send request with timing measurement."""
        record = RequestRecord()

        async for response in await self._client.chat.completions.create(
            **payload.model_dump(),
            stream=True,
            stream_options={"include_usage": True}
        ):
            record.response_timestamps_ns.append(time.time_ns())
            record.responses.append(response)

        return record

# Factory usage for dynamic client creation
def create_backend_client(config_dict: dict) -> BackendClientProtocol:
    """Create backend client from configuration."""
    # Parse configuration
    client_config = BackendClientConfig.model_validate(config_dict)

    # Factory creates appropriate client type
    return BackendClientFactory.create_backend_client(client_config)

# Configuration-driven client creation
openai_config = {
    "backend_client_type": "openai",
    "client_config": {
        "api_key": "sk-...",
        "url": "https://api.openai.com/v1",
        "model": "gpt-4",
        "max_tokens": 150,
        "temperature": 0.7,
        "api_type": "openai"
    }
}

# Create client instance
client = create_backend_client(openai_config)

# Generic client interface usage
formatted_payload = await client.format_payload(
    endpoint="v1/chat/completions",
    payload={"messages": [{"role": "user", "content": "Hello!"}]}
)

record = await client.send_request("v1/chat/completions", formatted_payload)
response = await client.parse_response(record)
```

## Visual Diagram

```mermaid
graph TB
    subgraph "Factory Pattern"
        BCF[BackendClientFactory] --> REG[Client Registry]
        REG --> |"@register decorator"| TYPES[Client Types]
    end

    subgraph "Client Types"
        OPENAI[OpenAI Client]
        GRPC[gRPC Client]
        HTTP[HTTP Client]
        DYNAMO[DynamoDB Client]
    end

    subgraph "Configuration Layer"
        BCC[BackendClientConfig] --> |Generic[ConfigT]| SPEC[Specific Configs]
        SPEC --> OAIC[OpenAIBackendClientConfig]
        SPEC --> GRPCC[GRPCBackendClientConfig]
        SPEC --> HTTPC[HTTPBackendClientConfig]
        SPEC --> DYNAMOC[DynamoBackendClientConfig]
    end

    subgraph "Protocol Interface"
        BCP[BackendClientProtocol] --> FP[format_payload]
        BCP --> SR[send_request]
        BCP --> PR[parse_response]
    end

    subgraph "Mixin Composition"
        BCCM[BackendClientConfigMixin] --> |provides| CONFIG[Configuration Access]
        OCM[OpenAIClientMixin] --> |provides| OAICLIENT[OpenAI Client Instance]
    end

    subgraph "Runtime Flow"
        USER[User Code] --> |config dict| BCF
        BCF --> |lookup| REG
        REG --> |instantiate| OPENAI
        OPENAI --> |implements| BCP
        OPENAI --> |uses| BCCM
        OPENAI --> |uses| OCM
    end

    style BCF fill:#ff9800
    style BCP fill:#4caf50
    style OPENAI fill:#2196f3
    style BCC fill:#9c27b0
```

## Best Practices and Pitfalls

**Best Practices:**
- Use the `@BackendClientFactory.register()` decorator for automatic client registration
- Implement all methods from `BackendClientProtocol` for consistent interface
- Leverage configuration mixins for shared functionality across client types
- Use Pydantic models for type-safe configuration validation
- Implement proper error handling in `send_request()` and `parse_response()` methods
- Use async/await patterns for non-blocking I/O operations
- Include comprehensive logging for debugging and monitoring

**Common Pitfalls:**
- Forgetting to register new client types with the factory
- Not implementing all required protocol methods
- Missing error handling for network failures or API errors
- Hardcoding configuration values instead of using Pydantic models
- Not handling different API response formats properly
- Blocking operations in async methods
- Insufficient timeout handling for external service calls

## Discussion Points

- How does the factory pattern improve maintainability compared to direct client instantiation?
- What are the trade-offs between using a centralized factory vs dependency injection for client management?
- How can we extend the factory pattern to support plugin-based backend client loading?

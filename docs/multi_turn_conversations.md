<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Multi-Turn Conversations in AIPerf

This document describes the enhanced multi-turn conversation support in AIPerf, designed to test chat-based AI models with proper conversation context management.

## Overview

AIPerf's multi-turn conversation system processes complete conversations (all turns) within a single credit, maintaining conversation context and producing multiple `RequestRecord` objects per conversation. This approach is architecturally clean and aligns well with the existing AIPerf framework.

## Architecture

### Core Principle: One Credit = One Complete Conversation

```
Credit Drop → Complete Conversation Processing → Multiple RequestRecords
     ↓              ↓                                    ↓
Single Credit → All Turns (1,2,3...N) → N RequestRecords
```

### Key Components

1. **ConversationCreditProcessorMixin** - Handles complete conversation processing
2. **Enhanced OpenAI Chat Converter** - Manages conversation history encoding
3. **ConversationWorker** - Optional worker implementation for conversations
4. **Multi-turn Dataset Support** - Already exists in the dataset layer

### Benefits of This Architecture

- ✅ **Simple State Management**: No cross-credit conversation state
- ✅ **Atomic Operations**: Complete conversations processed atomically
- ✅ **Clean Error Handling**: Failures affect only current conversation
- ✅ **Proper Context**: Full conversation history maintained
- ✅ **Multiple Records**: One record per turn for detailed metrics
- ✅ **Timing Respect**: Turn delays honored within conversations

## Implementation Details

### Conversation Processing Flow

```python
async def _process_credit_drop_internal(self, message: CreditDropMessage) -> CreditReturnMessage:
    """
    1. Get complete conversation from dataset manager
    2. Process all turns sequentially with context
    3. Generate one RequestRecord per turn
    4. Push all records to results pipeline
    5. Return credit to timing manager
    """
```

### Context Management

For chat completion APIs (OpenAI Chat Completions), the system:

1. **Builds Message History**: Accumulates user and assistant messages
2. **Encodes Context**: Converts history to JSON for request converter
3. **Maintains State**: Tracks conversation across all turns
4. **Updates History**: Adds model responses to context

### Request Converter Enhancement

The OpenAI chat completion converter now supports:

```python
# Standard single turn
{
    "messages": [
        {"role": "user", "content": "Hello"}
    ]
}

# Multi-turn with history
{
    "messages": [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "How are you?"}
    ]
}
```

## Dataset Format

Multi-turn conversations use the existing multi-turn dataset format:

```json
{
    "type": "multi_turn",
    "session_id": "conversation_001",
    "turns": [
        {
            "role": "user",
            "text": "Hello! How are you?",
            "delay": 0
        },
        {
            "role": "user",
            "text": "Can you help me with Python?",
            "delay": 2000
        },
        {
            "role": "user",
            "text": "What's the difference between lists and tuples?",
            "delay": 1500
        }
    ]
}
```

## Configuration

### Basic Configuration

```yaml
# Use existing timing modes - each credit = one conversation
loadgen:
  timing_mode: "request_rate"
  request_rate: 1.0  # 1 conversation per second
  request_count: 100 # Total conversations to process

# Dataset configuration
input:
  dataset:
    type: "custom"
    custom_type: "multi_turn"
    path: "./conversations.jsonl"

# Model configuration for chat completion
model:
  endpoint:
    type: "openai_chat_completions"
    url: "http://localhost:8000/v1/chat/completions"
```

### Conversation-Specific Settings

```yaml
conversation:
  turn:
    num: 10  # Maximum turns per conversation
    delay:
      mean: 1000   # Default delay between turns (ms)
      stddev: 200  # Variation in delays
```

## Usage Examples

### Using the Conversation Worker

```python
# Import the conversation worker
from aiperf.workers.conversation_worker import ConversationWorker

# Use in place of standard worker for multi-turn support
# (Manual instantiation - registration conflicts avoided)
```

### Using Enhanced Standard Worker

The standard worker automatically detects and processes multi-turn conversations when:

1. Dataset contains multi-turn conversations
2. Model endpoint is a chat completion API
3. Conversation history is properly encoded

### Running Multi-Turn Tests

```bash
# Create multi-turn dataset
python examples/multi_turn_chat_example.py

# Run AIPerf with the generated configuration
aiperf --config /tmp/multi_turn_config.json

# Observe multiple RequestRecords per conversation
```

## Metrics and Results

### Per-Turn Metrics

Each turn generates a separate `RequestRecord` with:

- `conversation_id`: Identifies the conversation
- `turn_index`: Position within conversation (0, 1, 2...)
- `timestamp_ns`: When the turn was processed
- `start_perf_ns`, `end_perf_ns`: Turn-specific timing
- `request`: The API payload with conversation history
- `responses`: Model response for this turn

### Conversation-Level Analysis

Analyze conversation patterns by:

```python
# Group records by conversation_id
conversation_records = records.groupby('conversation_id')

# Calculate conversation-level metrics
for conv_id, turns in conversation_records:
    total_latency = turns['end_perf_ns'].max() - turns['start_perf_ns'].min()
    turn_count = len(turns)
    avg_turn_latency = turns['latency'].mean()
```

## Technical Considerations

### Memory Management

- **No Persistent State**: Conversation context cleared after each conversation
- **Bounded Memory**: Each conversation processed independently
- **Clean Lifecycle**: Worker manages context lifetime

### Error Handling

- **Turn-Level Errors**: Individual turn failures don't stop conversation
- **Conversation-Level Errors**: Complete conversation failures generate error records
- **Graceful Degradation**: Remaining turns processed despite individual failures

### Performance

- **Sequential Processing**: Turns processed in order within conversation
- **Parallel Conversations**: Multiple workers can process different conversations
- **Timing Respect**: Turn delays and conversation timing honored

## Comparison with Alternative Approaches

| Approach | Pros | Cons |
|----------|------|------|
| **One Credit = Complete Conversation** ✅ | Simple, clean, atomic, no state management | Longer processing per credit |
| One Credit = One Turn | Fine-grained control | Complex state management, error handling |
| Separate Conversation Manager | Specialized handling | Additional complexity, state synchronization |

## Best Practices

### Dataset Design

1. **Realistic Conversations**: Mirror actual user interaction patterns
2. **Varied Lengths**: Mix short and long conversations
3. **Appropriate Delays**: Use realistic turn timing
4. **Context Dependency**: Design turns that build on previous responses

### Load Testing

1. **Conversation Rate**: Configure request rate as conversations per second
2. **Worker Scaling**: Scale workers based on conversation complexity
3. **Memory Monitoring**: Monitor worker memory usage during long conversations
4. **Context Length**: Be aware of model context limits

### Monitoring

1. **Turn Completion Rates**: Track successful turns per conversation
2. **Context Quality**: Monitor response relevance across turns
3. **Latency Patterns**: Analyze turn-to-turn latency variations
4. **Error Patterns**: Identify failure modes in conversation flow

## Migration from Single-Turn

For existing single-turn tests, migration is straightforward:

1. **Dataset Format**: Convert single turns to single-turn conversations
2. **Configuration**: No changes required to load generation settings
3. **Results**: Same `RequestRecord` format, just with conversation metadata
4. **Analysis**: Group by `conversation_id` for conversation-level metrics

## Future Enhancements

Potential improvements to the multi-turn system:

1. **Parallel Turn Processing**: For independent turns within conversations
2. **Conversation Templates**: Predefined conversation patterns
3. **Dynamic Turn Generation**: AI-generated follow-up questions
4. **Advanced Context Management**: Sliding window context for long conversations
5. **Conversation Branching**: Multiple response paths within conversations

---

This multi-turn conversation implementation provides a robust, scalable foundation for testing chat-based AI models while maintaining the simplicity and reliability of the AIPerf architecture.

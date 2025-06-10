<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# ZMQ Debug Logging Guide

This guide explains how to use the enhanced debug logging features to track down issues with `conversation_response` messages not being received by listeners.

## Quick Start

### 1. Enable Debug Logging

Add this to your application startup:

```python
from aiperf.common.comms.zmq.debug_utils import debug_conversation_response_flow
debug_conversation_response_flow()
```

### 2. Enable Broker Message Capture

If you're using a broker, add a capture address to monitor message flow:

```python
broker_config = BaseZMQDealerRouterBrokerConfig(
    frontend_address="tcp://*:5555",
    backend_address="tcp://*:5556",
    capture_address="tcp://*:5557"  # Add this for message monitoring
)
```

### 3. Run Your Application

Look for the log patterns described below to track your message flow.

## Log Patterns to Track

### Complete Message Flow

For a successful conversation_response, you should see this sequence:

1. **`DEALER[id] REQUEST START`** - Client sends request
2. **`DEALER[id] SENDING REQUEST`** - Request is sent to network
3. **`DEALER[id] BLOCKING ON RECV`** - Client waits for response
4. **`ROUTER[id] RECEIVED FRAMES`** - Router receives the request
5. **`ROUTER[id] HANDLING REQUEST`** - Router processes the request
6. **`ROUTER[id] SENDING RESPONSE`** - Router sends response
7. **`DEALER[id] RESPONSE RECEIVED`** - Client receives response
8. **`DEALER[id] REQUEST COMPLETE`** - Transaction completed

### If Broker is Used

With a broker, you'll also see:

- **`BROKER CAPTURED MESSAGE`** - Messages flowing through proxy
- **`BROKER CONVERSATION_RESPONSE DETECTED`** - Special attention to response messages

## Debugging Different Scenarios

### Scenario 1: Request Never Reaches Router

**Symptoms:**
- You see `DEALER[id] REQUEST START` and `DEALER[id] SENDING REQUEST`
- You never see `ROUTER[id] RECEIVED FRAMES`

**Debug Steps:**
1. Check if broker is running and bound to correct addresses
2. Verify DEALER is connecting to correct frontend address
3. Verify ROUTER is connecting to correct backend address
4. Check broker capture logs for the request message

### Scenario 2: Router Receives Request but Never Processes It

**Symptoms:**
- You see `ROUTER[id] RECEIVED FRAMES`
- You never see `ROUTER[id] HANDLING REQUEST`

**Debug Steps:**
1. Check if handler is registered for the message type
2. Look for `ROUTER[id] NO HANDLER` messages
3. Verify the `message_type` in the request matches registered handler

### Scenario 3: Router Processes Request but Never Sends Response

**Symptoms:**
- You see `ROUTER[id] HANDLING REQUEST` and `ROUTER[id] CALLING HANDLER`
- You never see `ROUTER[id] SENDING RESPONSE`

**Debug Steps:**
1. Check for `ROUTER[id] HANDLER EXCEPTION` messages
2. Verify your handler is returning a proper response message
3. Look for any uncaught exceptions in your handler code

### Scenario 4: Router Sends Response but Client Never Receives It

**Symptoms:**
- You see `ROUTER[id] RESPONSE SENT`
- You see `DEALER[id] STILL WAITING` (periodic updates)
- You never see `DEALER[id] RESPONSE RECEIVED`

**Debug Steps:**
1. **This is the most common issue** - check broker message capture
2. Look for `BROKER CONVERSATION_RESPONSE DETECTED` messages
3. Check the routing direction: should be `BACKEND->FRONTEND`
4. Verify the sender_id in the response matches the original request routing

## Advanced Debug Features

### Full Debug Trace

For maximum detail:

```python
from aiperf.common.comms.zmq.debug_utils import enable_full_debug_trace
enable_full_debug_trace()
```

### Session-Based Logging

Create a focused debug session:

```python
from aiperf.common.comms.zmq.debug_utils import create_debug_session_logger
logger = create_debug_session_logger("conversation_debug")
```

### Command Line Debug Setup

```bash
# Enable conversation response debugging
python -m aiperf.common.comms.zmq.debug_utils --mode conversation

# Enable full debug tracing
python -m aiperf.common.comms.zmq.debug_utils --mode full

# Save logs to file
python -m aiperf.common.comms.zmq.debug_utils --mode conversation --file zmq_debug.log
```

## Test Your Setup

Use the provided test script to verify debug logging is working:

```bash
python test_zmq_debug.py
```

This will test both direct DEALER-ROUTER communication and communication through a broker.

## Key Debug Information

### DEALER Client Logs

- **Request Timing**: Shows how long each request takes
- **Socket State**: Shows connection status and socket events
- **Periodic Updates**: Shows client is still waiting (every 5 seconds)
- **Response Analysis**: Shows response size and parsing details

### ROUTER Client Logs

- **Frame Analysis**: Detailed breakdown of multipart messages
- **Handler Execution**: Shows which handler was called and how long it took
- **Response Routing**: Shows the sender_id being used for response routing
- **Socket Events**: Shows any socket-level events

### Broker Logs

- **Message Direction**: Shows if messages are going frontend->backend or backend->frontend
- **Frame Structure**: Detailed analysis of multipart frame routing
- **Conversation Response Detection**: Special highlighting of response messages
- **Routing Analysis**: Shows how messages are being routed through the proxy

## Common Issues and Solutions

### Issue: Response Gets Lost in Broker

**Solution**: Check that the ROUTER is sending response to the correct sender_id. The broker logs will show the frame structure and routing direction.

### Issue: Multiple Frames Confuse Routing

**Solution**: Look at the detailed frame analysis in broker capture logs. The routing should preserve the original sender identity.

### Issue: Handler Exceptions Not Visible

**Solution**: Enable full debug trace to see detailed exception information from handlers.

### Issue: Socket Timeouts

**Solution**: Check the periodic "STILL WAITING" messages to see if the client is actually waiting or if there's a socket issue.

## Performance Impact

- **INFO Level**: Minimal impact, tracks key message events
- **DEBUG Level**: Moderate impact, shows detailed frame analysis
- **Message Capture**: Some overhead, but essential for broker debugging

For production debugging, use INFO level initially, then enable DEBUG or capture only when needed.

## Searching Logs

Use these patterns to search your logs:

```bash
# Follow a specific request ID
grep "0c7962928fbb4a34978f0459d7877342" your_log_file.log

# Find all conversation_response messages
grep "conversation_response" your_log_file.log

# Find broker routing issues
grep "BROKER.*CONVERSATION_RESPONSE" your_log_file.log

# Find timeouts
grep "TIMEOUT\|STILL WAITING" your_log_file.log
```

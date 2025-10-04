<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 14: ZMQ Communication

## Overview

ZeroMQ (ZMQ) forms the communication backbone of AIPerf, enabling high-performance, asynchronous message passing between distributed services. Unlike traditional message brokers that require dedicated infrastructure, ZMQ is a library that provides socket abstractions with built-in patterns for pub/sub, request/reply, and pipeline architectures. This chapter explores AIPerf's ZMQ architecture, socket types and patterns, proxy implementation, performance tuning, and best practices for distributed communication.

## ZMQ Architecture

### Why ZMQ?

AIPerf chose ZMQ over alternatives (gRPC, RabbitMQ, Redis Pub/Sub) for several reasons:

1. **High Performance**: No broker overhead, direct peer-to-peer communication
2. **Flexible Patterns**: Built-in support for pub/sub, req/rep, push/pull, dealer/router
3. **Backpressure Management**: Automatic flow control and queuing
4. **Transport Agnostic**: TCP, IPC, inproc supported transparently
5. **Minimal Dependencies**: Lightweight library, no external services required

### Communication Patterns

AIPerf uses multiple ZMQ patterns:

```
┌────────────────────────────────────────────────────────────┐
│                    PUB/SUB Pattern                         │
│  Timing Manager (PUB) ──────> All Services (SUB)          │
│  - Credit phase messages                                   │
│  - Progress updates                                        │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│                   PUSH/PULL Pattern                        │
│  Workers (PUSH) ──────> Record Processors (PULL)           │
│  - Inference results streaming                             │
│  - Load balanced across processors                         │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│                   DEALER/ROUTER Pattern                    │
│  Workers (DEALER) <────> Dataset Manager (ROUTER)          │
│  - Request/reply for dataset items                         │
│  - Fair queuing and load balancing                         │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│                    REQ/REP Pattern                         │
│  System Controller (REQ) <──> Services (REP)               │
│  - Command execution                                       │
│  - Synchronous responses                                   │
└────────────────────────────────────────────────────────────┘
```

### BaseZMQCommunication

Located in `/home/anthony/nvidia/projects/aiperf/aiperf/zmq/zmq_comms.py`:

```python
@implements_protocol(CommunicationProtocol)
class BaseZMQCommunication(BaseCommunication, AIPerfLoggerMixin, ABC):
    """ZeroMQ-based implementation of the CommunicationProtocol.

    Uses ZeroMQ for publish/subscribe, request/reply, and pull/push patterns
    to facilitate communication between AIPerf components.
    """

    def __init__(self, config: BaseZMQCommunicationConfig) -> None:
        super().__init__()
        self.config = config

        self.context = zmq.asyncio.Context.instance()
        self._clients_cache: dict[
            tuple[CommClientType, CommAddressType, bool], CommunicationClientProtocol
        ] = {}

        self.debug(f"ZMQ communication using protocol: {type(self.config).__name__}")

    def get_address(self, address_type: CommAddressType) -> str:
        """Get the actual address based on the address type from the config."""
        if isinstance(address_type, CommAddress):
            return self.config.get_address(address_type)
        return address_type

    def create_client(
        self,
        client_type: CommClientType,
        address: CommAddressType,
        bind: bool = False,
        socket_ops: dict | None = None,
        max_pull_concurrency: int | None = None,
        **kwargs,
    ) -> CommunicationClientProtocol:
        """Create a communication client for a given client type and address."""
        if (client_type, address, bind) in self._clients_cache:
            return self._clients_cache[(client_type, address, bind)]

        if self.state != LifecycleState.CREATED:
            raise InvalidStateError(
                f"Communication clients must be created before the "
                f"{self.__class__.__name__} class is initialized: {self.state!r}"
            )

        client = CommunicationClientFactory.create_instance(
            client_type,
            address=self.get_address(address),
            bind=bind,
            socket_ops=socket_ops,
            max_pull_concurrency=max_pull_concurrency,
            **kwargs,
        )

        self._clients_cache[(client_type, address, bind)] = client
        self.attach_child_lifecycle(client)
        return client
```

**Key Design:**

- **Singleton Context**: Single ZMQ context shared across all sockets
- **Client Caching**: Clients cached by (type, address, bind) tuple
- **Lifecycle Management**: Clients attached to parent lifecycle for proper cleanup
- **Factory Pattern**: Client creation delegated to factory

### Transport Types

**ZMQ TCP Transport:**

```python
@CommunicationFactory.register(CommunicationBackend.ZMQ_TCP)
class ZMQTCPCommunication(BaseZMQCommunication):
    """ZeroMQ-based implementation using TCP transport."""

    def __init__(self, config: ZMQTCPConfig | None = None) -> None:
        super().__init__(config or ZMQTCPConfig())
```

TCP addresses: `tcp://127.0.0.1:5555`

**ZMQ IPC Transport:**

```python
@CommunicationFactory.register(CommunicationBackend.ZMQ_IPC)
class ZMQIPCCommunication(BaseZMQCommunication):
    """ZeroMQ-based implementation using IPC transport."""

    def __init__(self, config: ZMQIPCConfig | None = None) -> None:
        super().__init__(config or ZMQIPCConfig())
        self._setup_ipc_directory()

    def _setup_ipc_directory(self) -> None:
        """Create IPC socket directory if using IPC transport."""
        self._ipc_socket_dir = Path(self.config.path)
        if not self._ipc_socket_dir.exists():
            self._ipc_socket_dir.mkdir(parents=True, exist_ok=True)

    @on_stop
    def _cleanup_ipc_sockets(self) -> None:
        """Clean up IPC socket files."""
        if self._ipc_socket_dir and self._ipc_socket_dir.exists():
            ipc_files = glob.glob(str(self._ipc_socket_dir / "*.ipc"))
            for ipc_file in ipc_files:
                if os.path.exists(ipc_file):
                    os.unlink(ipc_file)
```

IPC addresses: `ipc:///tmp/aiperf/pub.ipc`

**Transport Selection:**

- **TCP**: Distributed deployment across machines
- **IPC**: Single-machine deployment (lower latency, higher throughput)

## Socket Types and Patterns

### PUB/SUB Pattern

**Publisher (Timing Manager, System Controller):**

```python
pub_client = self.comms.create_pub_client(CommAddress.PUB)
await pub_client.publish(message)
```

**Subscriber (All Services):**

```python
sub_client = self.comms.create_sub_client(CommAddress.SUB)

@on_message(MessageType.CREDIT_PHASE_START)
async def handle_phase_start(self, msg: CreditPhaseStartMessage):
    # Handle message
    pass
```

**Characteristics:**

- **One-to-many**: Publisher sends to all subscribers
- **No acknowledgment**: Fire-and-forget semantics
- **Topic filtering**: Subscribers can filter by message type
- **Late joiners**: New subscribers miss earlier messages

**Use Cases:**

- Phase lifecycle events
- Progress updates
- Status broadcasts

### PUSH/PULL Pattern

**Pusher (Workers):**

```python
push_client = self.comms.create_push_client(CommAddress.RAW_INFERENCE_PROXY_FRONTEND)
await push_client.push(InferenceResultsMessage(...))
```

**Puller (Record Processors):**

```python
pull_client = self.comms.create_pull_client(
    CommAddress.RAW_INFERENCE_PROXY_BACKEND,
    bind=False,
    max_pull_concurrency=1000,
)

@on_pull_message(MessageType.INFERENCE_RESULTS)
async def handle_results(self, msg: InferenceResultsMessage):
    # Process results
    pass
```

**Characteristics:**

- **Pipeline**: Unidirectional data flow
- **Load balanced**: Messages distributed across pullers
- **Fair queuing**: Round-robin distribution
- **Backpressure**: Pullers signal when ready for more work

**Use Cases:**

- Streaming inference results from workers
- Distributing work across record processors

### DEALER/ROUTER Pattern

**Dealer (Workers):**

```python
dealer_client = self.comms.create_request_client(
    CommAddress.DATASET_MANAGER_PROXY_FRONTEND
)
response = await dealer_client.request(GetDatasetItemCommand(...))
```

**Router (Dataset Manager via Proxy):**

```python
router_client = self.comms.create_request_server(
    CommAddress.DATASET_MANAGER_PROXY_BACKEND,
    bind=True,
)

@on_command(CommandType.GET_DATASET_ITEM)
async def handle_request(self, cmd: GetDatasetItemCommand) -> DatasetItem:
    return self.get_item(cmd.conversation_id)
```

**Characteristics:**

- **Bidirectional**: Request/reply semantics
- **Asynchronous**: Multiple concurrent requests
- **Identity routing**: Router tracks dealer identities
- **Fair queuing**: Requests distributed across routers

**Use Cases:**

- Dataset item requests
- Command execution
- Stateful interactions

### REQ/REP Pattern

**Requester (System Controller):**

```python
req_client = self.comms.create_request_client(CommAddress.RECORDS_MANAGER)
result = await req_client.request(ProcessRecordsCommand())
```

**Replier (Records Manager):**

```python
rep_client = self.comms.create_request_server(CommAddress.RECORDS_MANAGER, bind=True)

@on_command(CommandType.PROCESS_RECORDS)
async def handle_command(self, cmd: ProcessRecordsCommand) -> ProcessRecordsResult:
    return await self._process_results()
```

**Characteristics:**

- **Synchronous**: Strict request/reply ordering
- **Lockstep**: Must alternate request/reply
- **No pipelining**: Cannot send multiple requests without replies
- **Simple**: Easy to reason about

**Use Cases:**

- Command/control operations
- Administrative tasks
- Debugging/testing

## Proxy Implementation

### Why Proxies?

ZMQ proxies enable:

1. **Decoupling**: Clients don't need to know about all servers
2. **Load Balancing**: Fair distribution across backends
3. **Scalability**: Add backends without client changes
4. **Monitoring**: Capture traffic for debugging

### BaseZMQProxy

Located in `/home/anthony/nvidia/projects/aiperf/aiperf/zmq/zmq_proxy_base.py`:

```python
class BaseZMQProxy(AIPerfLifecycleMixin, ABC):
    """A Base ZMQ Proxy class.

    - Frontend and backend sockets forward messages bidirectionally
    - Multiple clients CONNECT to frontend_address
    - Multiple services CONNECT to backend_address
    - Control: Optional REP socket for proxy commands
    - Monitoring: Optional PUB socket for traffic capture
    - Proxy runs in separate thread to avoid blocking event loop
    """

    def __init__(
        self,
        frontend_socket_class: type[BaseZMQClient],
        backend_socket_class: type[BaseZMQClient],
        zmq_proxy_config: BaseZMQProxyConfig,
        socket_ops: dict | None = None,
        proxy_uuid: str | None = None,
    ) -> None:
        self.proxy_uuid = proxy_uuid or uuid.uuid4().hex[:8]
        self.proxy_id = f"{self.__class__.__name__.lower()}_{self.proxy_uuid}"
        super().__init__()
        self.context = zmq.asyncio.Context.instance()

        self.frontend_address = zmq_proxy_config.frontend_address
        self.backend_address = zmq_proxy_config.backend_address
        self.control_address = zmq_proxy_config.control_address
        self.capture_address = zmq_proxy_config.capture_address

        self.backend_socket = backend_socket_class(
            address=self.backend_address,
            socket_ops=socket_ops,
            proxy_uuid=self.proxy_uuid,
        )

        self.frontend_socket = frontend_socket_class(
            address=self.frontend_address,
            socket_ops=socket_ops,
            proxy_uuid=self.proxy_uuid,
        )

        if self.control_address:
            self.control_client = ProxySocketClient(
                socket_type=SocketType.REP,
                address=self.control_address,
                socket_ops=socket_ops,
                end_type=ProxyEndType.Control,
                proxy_uuid=self.proxy_uuid,
            )

        if self.capture_address:
            self.capture_client = ProxySocketClient(
                socket_type=SocketType.PUB,
                address=self.capture_address,
                socket_ops=socket_ops,
                end_type=ProxyEndType.Capture,
                proxy_uuid=self.proxy_uuid,
            )
```

### Proxy Types

**PULL/PUSH Proxy (for inference results):**

```python
class PullPushProxy(BaseZMQProxy):
    """Proxy for PULL/PUSH pattern (pipeline)."""

    def __init__(self, config: PullPushProxyConfig):
        super().__init__(
            frontend_socket_class=RouterSocket,  # Workers PUSH here
            backend_socket_class=DealerSocket,   # Record Processors PULL here
            zmq_proxy_config=config,
        )
```

**DEALER/ROUTER Proxy (for dataset requests):**

```python
class DealerRouterProxy(BaseZMQProxy):
    """Proxy for DEALER/ROUTER pattern (async req/rep)."""

    def __init__(self, config: DealerRouterProxyConfig):
        super().__init__(
            frontend_socket_class=RouterSocket,  # Workers DEALER here
            backend_socket_class=DealerSocket,   # Dataset Manager ROUTER here
            zmq_proxy_config=config,
        )
```

### Proxy Operation

```python
@on_start
async def _start_proxy(self) -> None:
    """Start the ZMQ proxy."""
    self.proxy_task = asyncio.create_task(self._run_proxy())

async def _run_proxy(self) -> None:
    """Run the ZMQ proxy loop."""
    try:
        await zmq.proxy(
            self.frontend_socket.socket,
            self.backend_socket.socket,
            self.capture_client.socket if self.capture_client else None,
        )
    except asyncio.CancelledError:
        self.debug("Proxy loop cancelled")
    except Exception as e:
        self.error(f"Proxy loop error: {e}")

@on_stop
async def _stop_proxy(self) -> None:
    """Stop the ZMQ proxy."""
    if self.proxy_task:
        self.proxy_task.cancel()
        try:
            await self.proxy_task
        except asyncio.CancelledError:
            pass
```

**Proxy Loop:**

```
Frontend (ROUTER)  ←──────────────→  Backend (DEALER)
      ↑                                      ↓
   PUSH from                             PULL by
    Workers                          Record Processors
```

The `zmq.proxy()` call is a blocking operation that forwards messages bidirectionally.

## Performance Tuning

### Socket Options

```python
socket_ops = {
    "ZMQ_SNDHWM": 10000,        # Send high water mark (queue size)
    "ZMQ_RCVHWM": 10000,        # Receive high water mark
    "ZMQ_LINGER": 0,            # Discard pending messages on close
    "ZMQ_IMMEDIATE": 1,         # Don't queue for disconnected peers
    "ZMQ_MAXMSGSIZE": 10485760, # Max message size (10 MB)
    "ZMQ_SNDBUF": 131072,       # OS send buffer (128 KB)
    "ZMQ_RCVBUF": 131072,       # OS receive buffer (128 KB)
}

client = comms.create_client(
    client_type=CommClientType.PUB,
    address=CommAddress.PUB,
    socket_ops=socket_ops,
)
```

**Key Options:**

- **HWM (High Water Mark)**: Queue size before blocking/dropping. Higher = more buffering, more memory.
- **LINGER**: How long to wait for pending messages on close. 0 = discard immediately.
- **IMMEDIATE**: Whether to queue for disconnected peers. 1 = drop if no peer.
- **MAXMSGSIZE**: Maximum message size. Protects against malformed messages.
- **SNDBUF/RCVBUF**: OS-level socket buffers. Larger = better burst handling.

### I/O Threads

```python
context = zmq.asyncio.Context.instance()
context.set(zmq.IO_THREADS, 4)  # Number of I/O threads
```

**Tuning:**

- **1 thread**: Sufficient for most workloads (default)
- **2-4 threads**: High throughput scenarios (>100k msg/sec)
- **>4 threads**: Rarely beneficial, may hurt performance

### Message Serialization

AIPerf uses Pydantic models with JSON serialization:

```python
# Sending
message_json = message.model_dump_json()
await socket.send_string(message_json)

# Receiving
message_json = await socket.recv_string()
message = Message.from_json(message_json)
```

**Performance:**

- **JSON**: Human-readable, ~1-2 MB/s per core
- **MessagePack**: More efficient, ~5-10 MB/s per core (future)
- **Pickle**: Fastest, ~20-50 MB/s per core (Python-only)

### Batching

For high-rate scenarios, batch messages:

```python
async def send_batch(self, messages: list[Message]) -> None:
    """Send multiple messages in a single ZMQ message."""
    batch = [msg.model_dump_json() for msg in messages]
    await self.socket.send_json(batch)

async def receive_batch(self) -> list[Message]:
    """Receive a batch of messages."""
    batch = await self.socket.recv_json()
    return [Message.from_json(msg_json) for msg_json in batch]
```

Batching reduces syscalls and ZMQ overhead.

### Compression

For large messages, enable compression:

```python
import zlib

async def send_compressed(self, message: Message) -> None:
    """Send a compressed message."""
    data = message.model_dump_json().encode()
    compressed = zlib.compress(data)
    await self.socket.send(compressed)

async def receive_compressed(self) -> Message:
    """Receive a compressed message."""
    compressed = await self.socket.recv()
    data = zlib.decompress(compressed)
    return Message.from_json(data)
```

Compression reduces network bandwidth but increases CPU usage.

## Best Practices

### Connection Management

**Always use lifecycle hooks:**

```python
@on_init
async def _initialize_comms(self) -> None:
    """Initialize ZMQ clients."""
    self.pub_client = self.comms.create_pub_client(CommAddress.PUB)
    self.sub_client = self.comms.create_sub_client(CommAddress.SUB)

@on_stop
async def _cleanup_comms(self) -> None:
    """Clean up ZMQ clients."""
    # Clients auto-cleaned via lifecycle attachment
    pass
```

**Avoid creating clients in loops:**

```python
# Bad
for i in range(1000):
    client = comms.create_pub_client(...)  # Creates 1000 clients!
    await client.publish(msg)

# Good
client = comms.create_pub_client(...)
for i in range(1000):
    await client.publish(msg)
```

### Error Handling

**Handle ZMQError gracefully:**

```python
import zmq

try:
    await socket.send_string(message_json)
except zmq.ZMQError as e:
    if e.errno == zmq.EAGAIN:
        # Would block, retry later
        await asyncio.sleep(0.01)
    elif e.errno == zmq.ETERM:
        # Context terminated, exit gracefully
        return
    else:
        # Other error, log and continue
        self.error(f"ZMQ error: {e}")
```

### Message Ordering

**PUB/SUB**: No ordering guarantees across topics

```python
# May arrive out of order
await pub.publish(CreditPhaseStartMessage(...))
await pub.publish(CreditPhaseProgressMessage(...))
```

**PUSH/PULL**: Ordering preserved per sender

```python
# Worker A's messages arrive in order
# Worker B's messages arrive in order
# But A and B may interleave
```

**DEALER/ROUTER**: Ordering per dealer

```python
# Worker A's requests/replies in order
# Worker B's requests/replies in order
```

### Slow Subscriber Problem

PUB/SUB suffers from "slow subscriber" issue:

```
Publisher (fast) ──────> Subscriber A (fast)
                    └───> Subscriber B (SLOW)
```

If Subscriber B is slow, it may drop messages or block the publisher.

**Solutions:**

1. **Use XPUB/XSUB**: Allows backpressure signaling
2. **Dedicated threads**: Run slow subscribers in separate threads
3. **Drop messages**: Set HWM to drop old messages

## Troubleshooting

### Address Already in Use

**Symptoms:** `zmq.error.ZMQError: Address already in use`

**Causes:**
1. Previous process didn't clean up IPC socket
2. Multiple processes binding to same address
3. Insufficient cleanup time

**Solutions:**

```python
# For IPC, clean up socket files
@on_stop
def _cleanup_ipc(self) -> None:
    if os.path.exists(self.ipc_path):
        os.unlink(self.ipc_path)

# For TCP, use SO_REUSEADDR
socket.setsockopt(zmq.REUSEADDR, 1)
```

### Lost Messages

**Symptoms:** Messages not received by subscribers/pullers

**Causes:**
1. Slow subscriber dropped messages (HWM reached)
2. Late joiner (SUB) missed early messages
3. Network partition

**Solutions:**

```python
# Increase HWM
socket.setsockopt(zmq.RCVHWM, 100000)

# For PUB/SUB, use synchronization
# Publisher waits for all subscribers before sending
```

### High Latency

**Symptoms:** Messages take seconds to arrive

**Causes:**
1. HWM reached, blocking sender
2. Large messages, slow serialization
3. Network congestion

**Solutions:**

```python
# Increase HWM
socket.setsockopt(zmq.SNDHWM, 100000)

# Use compression for large messages
# Switch to IPC if single-machine

# Monitor queue depth
queue_depth = socket.getsockopt(zmq.EVENTS)
```

## Key Takeaways

1. **ZMQ Patterns**: AIPerf uses PUB/SUB (broadcasts), PUSH/PULL (pipelines), DEALER/ROUTER (async req/rep), and REQ/REP (sync req/rep) patterns.

2. **Transport Types**: TCP for distributed deployment, IPC for single-machine (lower latency).

3. **Proxy Architecture**: Proxies decouple clients from servers, enable load balancing, and provide monitoring capabilities.

4. **Singleton Context**: Single ZMQ context shared across all sockets for efficiency.

5. **Socket Options**: Tune HWM, LINGER, IMMEDIATE, MAXMSGSIZE, SNDBUF, RCVBUF for performance.

6. **I/O Threads**: 1 thread sufficient for most workloads, 2-4 for extreme throughput.

7. **Message Serialization**: JSON (current), MessagePack/Pickle (future) for better performance.

8. **Batching**: Reduce syscall overhead by batching multiple messages.

9. **Slow Subscriber Problem**: PUB/SUB may drop messages if subscribers can't keep up; use XPUB/XSUB or dedicated threads.

10. **Lifecycle Management**: Always use lifecycle hooks for client creation/cleanup to prevent resource leaks.

Next: [Chapter 15: Message System](chapter-15-message-system.md)

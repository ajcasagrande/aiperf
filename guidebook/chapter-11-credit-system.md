<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 11: Credit System

## Overview

The Credit System is the heart of AIPerf's flow control mechanism, implementing a sophisticated credit-based semaphore pattern that enables precise control over request timing and rate limiting. Rather than using simple timers or unbounded concurrency, AIPerf uses a credit metaphor where each request requires a "credit" to be executed. This design provides several critical capabilities:

- **Precise timing control**: Credits can be dropped at exact nanosecond timestamps
- **Backpressure management**: Workers request credits and wait if none are available
- **Phase-based execution**: Different benchmark phases (warmup vs profiling) with distinct behaviors
- **Graceful completion**: Tracks in-flight requests and ensures clean phase transitions
- **Request cancellation**: Supports time-limited requests for timeout testing

This chapter provides a comprehensive deep dive into the credit system architecture, implementation patterns, lifecycle management, and performance implications.

## Credit System Architecture

### Core Components

The credit system consists of several interconnected components:

```
┌─────────────────────────────────────────────────────────────┐
│                      Timing Manager                          │
│  ┌────────────────────────────────────────────────────┐     │
│  │         Credit Issuing Strategy                    │     │
│  │  ┌──────────────────────────────────────────┐     │     │
│  │  │  Phase Configs & Stats                   │     │     │
│  │  │  - Warmup Phase                          │     │     │
│  │  │  - Profiling Phase                       │     │     │
│  │  │  - Duration or Count Based               │     │     │
│  │  └──────────────────────────────────────────┘     │     │
│  │                                                     │     │
│  │  ┌──────────────────────────────────────────┐     │     │
│  │  │  Credit Manager Protocol                 │     │     │
│  │  │  - drop_credit()                         │     │     │
│  │  │  - publish_progress()                    │     │     │
│  │  │  - publish_phase_start()                 │     │     │
│  │  │  - publish_phase_complete()              │     │     │
│  │  └──────────────────────────────────────────┘     │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Credit Messages
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Message Bus (ZMQ)                         │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ CreditDropMessage
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                         Workers                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │  Credit Processor                                  │     │
│  │  - Receive credit drops                            │     │
│  │  - Execute requests at precise times               │     │
│  │  - Return credits via CreditReturnMessage          │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### Credit Manager Protocol

The `CreditManagerProtocol` defines the interface for credit management operations. Located in `/home/anthony/nvidia/projects/aiperf/aiperf/timing/credit_manager.py`, it provides the contract that any credit-issuing component must implement:

```python
@runtime_checkable
class CreditManagerProtocol(PubClientProtocol, Protocol):
    """Defines the interface for a CreditManager.

    This is used to allow the credit issuing strategy to interact with
    the TimingManager in a decoupled way.
    """

    async def drop_credit(
        self,
        credit_phase: CreditPhase,
        conversation_id: str | None = None,
        credit_drop_ns: int | None = None,
        *,
        should_cancel: bool = False,
        cancel_after_ns: int = 0,
    ) -> None: ...

    async def publish_progress(
        self, phase: CreditPhase, sent: int, completed: int
    ) -> None: ...

    async def publish_credits_complete(self) -> None: ...

    async def publish_phase_start(
        self,
        phase: CreditPhase,
        start_ns: int,
        total_expected_requests: int | None,
        expected_duration_sec: float | None,
    ) -> None: ...

    async def publish_phase_sending_complete(
        self, phase: CreditPhase, sent_end_ns: int, sent: int
    ) -> None: ...

    async def publish_phase_complete(
        self,
        phase: CreditPhase,
        completed: int,
        end_ns: int,
        timeout_triggered: bool = False,
    ) -> None: ...
```

The protocol decouples credit issuance from the timing manager implementation, allowing different strategies to be plugged in.

## Credit Models

### CreditPhaseConfig

The `CreditPhaseConfig` model defines how a credit phase should behave. Located in `/home/anthony/nvidia/projects/aiperf/aiperf/common/models/credit_models.py`:

```python
class CreditPhaseConfig(AIPerfBaseModel):
    """Model for phase credit config. This is used by the TimingManager to
    configure the credit phases."""

    type: CreditPhase = Field(..., description="The type of credit phase")
    total_expected_requests: int | None = Field(
        default=None,
        ge=1,
        description="The total number of expected credits. If None, the phase is not request count based.",
    )
    expected_duration_sec: float | None = Field(
        default=None,
        ge=1,
        description="The expected duration of the credit phase in seconds. If None, the phase is not time based.",
    )

    @property
    def is_time_based(self) -> bool:
        return self.expected_duration_sec is not None

    @property
    def is_request_count_based(self) -> bool:
        return self.total_expected_requests is not None

    @property
    def is_valid(self) -> bool:
        """A phase config is valid if it is exactly one of the following:
        - is_time_based (expected_duration_sec is set and > 0)
        - is_request_count_based (total_expected_requests is set and > 0)
        """
        is_time_based = self.is_time_based
        is_request_count_based = self.is_request_count_based
        return (is_time_based and not is_request_count_based) or (
            not is_time_based and is_request_count_based
        )
```

**Key Design Decisions:**

1. **Mutually Exclusive Modes**: A phase is either time-based OR count-based, never both
2. **Validation**: The `is_valid` property ensures configuration consistency
3. **Flexibility**: Different phases can use different modes (warmup might be count-based while profiling is time-based)

### CreditPhaseStats

`CreditPhaseStats` extends `CreditPhaseConfig` to track runtime statistics:

```python
class CreditPhaseStats(CreditPhaseConfig):
    """Model for phase credit stats. Extends the CreditPhaseConfig fields to
    track the progress of the credit phases."""

    start_ns: int | None = Field(
        default=None,
        description="The start time of the credit phase in nanoseconds.",
    )
    sent_end_ns: int | None = Field(
        default=None,
        description="The time of the last sent credit in nanoseconds.",
    )
    end_ns: int | None = Field(
        default=None,
        ge=1,
        description="The time in which the last credit was returned from workers.",
    )
    sent: int = Field(default=0, description="The number of sent credits")
    completed: int = Field(
        default=0,
        description="The number of completed credits (returned from workers)",
    )

    @property
    def is_sending_complete(self) -> bool:
        return self.sent_end_ns is not None

    @property
    def is_complete(self) -> bool:
        return self.is_sending_complete and self.end_ns is not None

    @property
    def in_flight(self) -> int:
        """Calculate the number of in-flight credits (sent but not completed)."""
        return self.sent - self.completed

    def should_send(self) -> bool:
        """Whether the phase should send more credits."""
        if self.total_expected_requests is not None:
            return self.sent < self.total_expected_requests
        elif self.expected_duration_sec is not None:
            return time.time_ns() - self.start_ns <= (
                self.expected_duration_sec * NANOS_PER_SECOND
            )
        else:
            raise InvalidStateError("Credit phase is not time or request count based")

    @property
    def progress_percent(self) -> float | None:
        if self.start_ns is None:
            return None

        if self.is_complete:
            return 100

        if self.is_time_based:
            # Time based, so progress is the percentage of time elapsed
            return (
                (time.time_ns() - self.start_ns)
                / (self.expected_duration_sec * NANOS_PER_SECOND)
            ) * 100

        elif self.total_expected_requests is not None:
            # Credit count based, so progress is the percentage of credits returned
            return (self.completed / self.total_expected_requests) * 100

        return None
```

**State Tracking:**

- `sent`: Credits issued to workers
- `completed`: Credits returned by workers
- `in_flight`: Difference between sent and completed
- `start_ns`, `sent_end_ns`, `end_ns`: Timeline markers for phase lifecycle

## Credit Messages

### CreditDropMessage

The `CreditDropMessage` is sent from the Timing Manager to workers, authorizing a request. Located in `/home/anthony/nvidia/projects/aiperf/aiperf/common/messages/credit_messages.py`:

```python
class CreditDropMessage(BaseServiceMessage):
    """Message indicating that a credit has been dropped.
    This message is sent by the timing manager to workers to indicate that
    credit(s) have been dropped.
    """

    message_type: MessageTypeT = MessageType.CREDIT_DROP

    request_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="The ID of the credit drop, that will be used as the X-Correlation-ID header.",
    )
    phase: CreditPhase = Field(..., description="The type of credit phase")
    conversation_id: str | None = Field(
        default=None, description="The ID of the conversation, if applicable."
    )
    credit_drop_ns: int | None = Field(
        default=None,
        description="Timestamp of the credit drop, if applicable. None means send ASAP.",
    )
    should_cancel: bool = Field(
        default=False,
        description="Whether this request should be cancelled after the specified delay.",
    )
    cancel_after_ns: int = Field(
        default=0,
        ge=0,
        description="Delay in nanoseconds after which the request should be cancelled.",
    )
```

**Key Fields:**

- `request_id`: Unique identifier that becomes the X-Correlation-ID header for traceability
- `credit_drop_ns`: When `None`, the worker sends immediately; when set, worker waits until that precise timestamp
- `should_cancel`: Enables timeout testing by cancelling the request after a specified delay
- `conversation_id`: Links credits to multi-turn conversations

### CreditReturnMessage

Workers send this message back to the Timing Manager when work completes:

```python
class CreditReturnMessage(BaseServiceMessage):
    """Message indicating that a credit has been returned.
    This message is sent by a worker to the timing manager to indicate that
    work has been completed.
    """

    message_type: MessageTypeT = MessageType.CREDIT_RETURN

    phase: CreditPhase = Field(
        ...,
        description="The Credit Phase of the credit drop.",
    )
    credit_drop_id: str = Field(
        ...,
        description="ID of the credit drop, that defines the X-Correlation-ID header.",
    )
    delayed_ns: int | None = Field(
        default=None,
        ge=1,
        description="The number of nanoseconds the credit drop was delayed by.",
    )

    @property
    def delayed(self) -> bool:
        return self.delayed_ns is not None
```

The `delayed_ns` field tracks timing precision - if the worker couldn't send the request at the exact scheduled time, this records how much it was delayed.

### Phase Lifecycle Messages

AIPerf publishes several messages to track phase lifecycle:

**CreditPhaseStartMessage**: Signals the beginning of a phase

```python
class CreditPhaseStartMessage(BaseServiceMessage):
    message_type: MessageTypeT = MessageType.CREDIT_PHASE_START
    phase: CreditPhase = Field(..., description="The type of credit phase")
    start_ns: int = Field(ge=1, description="The start time in nanoseconds.")
    total_expected_requests: int | None = Field(
        default=None, ge=1,
        description="The total number of expected requests (if count-based).",
    )
    expected_duration_sec: float | None = Field(
        default=None, ge=1,
        description="The expected duration in seconds (if time-based).",
    )
```

**CreditPhaseProgressMessage**: Periodic progress updates

```python
class CreditPhaseProgressMessage(BaseServiceMessage):
    message_type: MessageTypeT = MessageType.CREDIT_PHASE_PROGRESS
    phase: CreditPhase = Field(..., description="The type of credit phase")
    sent: int = Field(..., ge=0, description="The number of sent credits")
    completed: int = Field(..., ge=0, description="The number of completed credits")
```

**CreditPhaseSendingCompleteMessage**: All credits have been dropped

```python
class CreditPhaseSendingCompleteMessage(BaseServiceMessage):
    message_type: MessageTypeT = MessageType.CREDIT_PHASE_SENDING_COMPLETE
    phase: CreditPhase = Field(..., description="The type of credit phase")
    sent_end_ns: int = Field(..., ge=1, description="The time of the last sent credit.")
    sent: int = Field(..., ge=0, description="The final number of sent credits.")
```

**CreditPhaseCompleteMessage**: All work has finished

```python
class CreditPhaseCompleteMessage(BaseServiceMessage):
    message_type: MessageTypeT = MessageType.CREDIT_PHASE_COMPLETE
    phase: CreditPhase = Field(..., description="The type of credit phase")
    completed: int = Field(..., ge=0, description="The final count of completed credits.")
    end_ns: int = Field(..., ge=1, description="The time the last credit was returned.")
    timeout_triggered: bool = Field(
        default=False,
        description="Whether this phase completed because a timeout was triggered",
    )
```

**CreditsCompleteMessage**: All phases finished

```python
class CreditsCompleteMessage(BaseServiceMessage):
    message_type: MessageTypeT = MessageType.CREDITS_COMPLETE
```

## Credit Issuing Strategy

### Base Strategy Pattern

The `CreditIssuingStrategy` is an abstract base class that defines the credit issuance pattern. Located in `/home/anthony/nvidia/projects/aiperf/aiperf/timing/credit_issuing_strategy.py`:

```python
class CreditIssuingStrategy(TaskManagerMixin, ABC):
    """
    Base class for credit issuing strategies.
    """

    def __init__(
        self, config: TimingManagerConfig, credit_manager: CreditManagerProtocol
    ):
        super().__init__()
        self.config = config
        self.credit_manager = credit_manager

        self.cancellation_strategy = RequestCancellationStrategy(config)

        # This event is set when all phases are complete
        self.all_phases_complete_event = asyncio.Event()

        # This event is set when a single phase is complete
        self.phase_complete_event = asyncio.Event()

        # The running stats for each phase, keyed by phase type.
        self.phase_stats: dict[CreditPhase, CreditPhaseStats] = {}

        # The phases to run including their configuration, in order of execution.
        self.ordered_phase_configs: list[CreditPhaseConfig] = []

        self._setup_phase_configs()
        self._validate_phase_configs()
```

### Phase Configuration Setup

The strategy sets up warmup and profiling phases:

```python
def _setup_phase_configs(self) -> None:
    """Setup the phases for the strategy. This can be overridden in subclasses."""
    self._setup_warmup_phase_config()
    self._setup_profiling_phase_config()
    self.info(
        lambda: f"Credit issuing strategy {self.__class__.__name__} initialized "
        f"with {len(self.ordered_phase_configs)} phase(s): {self.ordered_phase_configs}"
    )

def _setup_warmup_phase_config(self) -> None:
    """Setup the warmup phase."""
    if self.config.warmup_request_count > 0:
        self.ordered_phase_configs.append(
            CreditPhaseConfig(
                type=CreditPhase.WARMUP,
                total_expected_requests=self.config.warmup_request_count,
            )
        )

def _setup_profiling_phase_config(self) -> None:
    """Setup the profiling phase."""
    if self.config.benchmark_duration is not None:
        self.debug(
            f"Setting up duration-based profiling phase: "
            f"expected_duration_sec={self.config.benchmark_duration}"
        )
        self.ordered_phase_configs.append(
            CreditPhaseConfig(
                type=CreditPhase.PROFILING,
                expected_duration_sec=self.config.benchmark_duration,
            )
        )
    else:
        self.debug(
            f"Setting up count-based profiling phase: "
            f"total_expected_requests={self.config.request_count}"
        )
        self.ordered_phase_configs.append(
            CreditPhaseConfig(
                type=CreditPhase.PROFILING,
                total_expected_requests=self.config.request_count,
            )
        )
```

### Strategy Execution

The strategy executes phases sequentially:

```python
async def start(self) -> None:
    """Start the credit issuing strategy. This will launch the progress reporting
    loop, the warmup phase (if applicable), and the profiling phase, all in the
    background."""
    self.debug(
        lambda: f"Starting credit issuing strategy {self.__class__.__name__}"
    )
    self.all_phases_complete_event.clear()

    # Start the progress reporting loop in the background
    self.execute_async(self._progress_report_loop())

    # Execute the phases in the background
    self.execute_async(self._execute_phases())

    self.debug(
        lambda: f"Waiting for all credit phases to complete for "
        f"{self.__class__.__name__}"
    )
    # Wait for all phases to complete before returning
    await self.all_phases_complete_event.wait()
    self.debug(lambda: f"All credit phases completed for {self.__class__.__name__}")

async def _execute_phases(self) -> None:
    """Execute all of the credit phases sequentially."""
    for phase_config in self.ordered_phase_configs:
        self.phase_complete_event.clear()

        phase_stats = CreditPhaseStats.from_phase_config(phase_config)
        phase_stats.start_ns = time.time_ns()
        self.phase_stats[phase_config.type] = phase_stats

        self.execute_async(
            self.credit_manager.publish_phase_start(
                phase_config.type,
                phase_stats.start_ns,
                phase_config.total_expected_requests,
                phase_config.expected_duration_sec,
            )
        )

        # This is implemented in subclasses
        await self._execute_single_phase(phase_stats)

        # We have sent all the credits for this phase, but we still need to
        # wait for the credits to be returned
        phase_stats.sent_end_ns = time.time_ns()
        self.execute_async(
            self.credit_manager.publish_phase_sending_complete(
                phase_config.type, phase_stats.sent_end_ns, phase_stats.sent
            )
        )

        # Wait for the credits to be returned before continuing to the next phase
        await self._wait_for_phase_completion(phase_stats)
```

The `_execute_single_phase()` method is abstract and implemented by concrete strategies (like `ConcurrencyStrategy`, `FixedRateStrategy`, or `PoissonStrategy`).

### Phase Completion Handling

The strategy must wait for all credits to be returned before moving to the next phase:

```python
async def _wait_for_phase_completion(self, phase_stats: CreditPhaseStats) -> None:
    """Wait for a phase to complete, with timeout for time-based phases."""
    if phase_stats.is_time_based:
        # For time-based phases, calculate how much time is left from the
        # original duration
        elapsed_ns = time.time_ns() - phase_stats.start_ns
        elapsed_sec = elapsed_ns / NANOS_PER_SECOND
        remaining_sec = max(0, phase_stats.expected_duration_sec - elapsed_sec)

        grace_period = self.config.benchmark_grace_period
        total_timeout = remaining_sec + grace_period

        if grace_period > 0 and remaining_sec <= 0:
            self.info(
                f"Benchmark duration elapsed for {phase_stats.type} phase, "
                f"entering {grace_period}s grace period"
            )

            # Check if phase is already complete before starting grace period wait
            if phase_stats.in_flight == 0:
                self.info(
                    f"Phase {phase_stats.type} has no in-flight requests, "
                    f"skipping grace period"
                )
                await self._force_phase_completion(
                    phase_stats, grace_period_timeout=False
                )
                return

        # Wait for either phase completion or timeout
        try:
            await asyncio.wait_for(
                self.phase_complete_event.wait(), timeout=total_timeout
            )
            # Phase completed naturally
            return
        except asyncio.TimeoutError:
            # Total timeout elapsed, force completion
            if grace_period > 0 and remaining_sec <= 0:
                self.info(
                    f"Grace period timeout elapsed for {phase_stats.type} phase"
                )
                await self._force_phase_completion(
                    phase_stats, grace_period_timeout=True
                )
            else:
                self.info(
                    f"Total timeout ({phase_stats.expected_duration_sec}s + "
                    f"{grace_period}s grace) elapsed for {phase_stats.type} phase"
                )
                await self._force_phase_completion(
                    phase_stats, grace_period_timeout=True
                )
    else:
        # For request-count-based phases, wait indefinitely
        await self.phase_complete_event.wait()
```

**Grace Period Logic:**

For time-based phases, AIPerf implements a grace period to handle requests that started before the duration expired but haven't completed yet:

1. Calculate remaining time in the benchmark duration
2. Add a configurable grace period (default from config)
3. Wait up to `total_timeout = remaining_time + grace_period`
4. If timeout expires, force phase completion

### Credit Return Handling

When workers return credits, the strategy updates stats and checks for phase completion:

```python
async def _on_credit_return(self, message: CreditReturnMessage) -> None:
    """This is called by the credit manager when a credit is returned."""
    if message.phase not in self.phase_stats:
        self.debug(
            f"Credit return message received for phase {message.phase} but "
            f"no phase stats found"
        )
        return

    phase_stats = self.phase_stats[message.phase]
    phase_stats.completed += 1

    # Check if this phase is complete
    is_phase_complete = False
    if phase_stats.is_sending_complete:
        if phase_stats.is_request_count_based:
            # Request-count-based: complete when all requests are returned
            is_phase_complete = (
                phase_stats.completed >= phase_stats.total_expected_requests
            )
        else:
            # Time-based: complete when all in-flight requests complete before
            # the timeout. Duration timeout is handled separately with
            # force_phase_completion.
            is_phase_complete = phase_stats.in_flight == 0

    if is_phase_complete:
        phase_stats.end_ns = time.time_ns()
        self.notice(f"Phase completed: {phase_stats}")

        self.execute_async(
            self.credit_manager.publish_phase_complete(
                message.phase, phase_stats.completed, phase_stats.end_ns
            )
        )

        self.phase_complete_event.set()

        if phase_stats.type == CreditPhase.PROFILING:
            await self.credit_manager.publish_credits_complete()
            self.all_phases_complete_event.set()

        # We don't need to keep track of the phase stats anymore
        self.phase_stats.pop(message.phase)
```

**Completion Conditions:**

- **Count-based phases**: Complete when `completed >= total_expected_requests`
- **Time-based phases**: Complete when `in_flight == 0` (all requests returned)

### Progress Reporting

A background loop periodically publishes progress:

```python
async def _progress_report_loop(self) -> None:
    """Report the progress at a fixed interval."""
    self.debug("Starting progress reporting loop")
    while not self.all_phases_complete_event.is_set():
        await asyncio.sleep(DEFAULT_CREDIT_PROGRESS_REPORT_INTERVAL)

        for phase, stats in self.phase_stats.items():
            try:
                await self.credit_manager.publish_progress(
                    phase, stats.sent, stats.completed
                )
            except Exception as e:
                self.error(f"Error publishing credit progress: {e}")
            except asyncio.CancelledError:
                self.debug("Credit progress reporting loop cancelled")
                return

    self.debug("All credits completed, stopping credit progress reporting loop")
```

The default interval is defined in constants (typically 1 second).

## Credit Phase Lifecycle

### Phase States

Each credit phase transitions through several states:

```
1. CREATED
   ↓
2. STARTED (start_ns set, publish CreditPhaseStartMessage)
   ↓
3. SENDING (credits being dropped to workers)
   ↓
4. SENDING_COMPLETE (sent_end_ns set, publish CreditPhaseSendingCompleteMessage)
   ↓
5. COMPLETE (end_ns set, publish CreditPhaseCompleteMessage)
```

### State Transitions

**CREATED → STARTED:**

```python
phase_stats = CreditPhaseStats.from_phase_config(phase_config)
phase_stats.start_ns = time.time_ns()
self.phase_stats[phase_config.type] = phase_stats

self.execute_async(
    self.credit_manager.publish_phase_start(
        phase_config.type,
        phase_stats.start_ns,
        phase_config.total_expected_requests,
        phase_config.expected_duration_sec,
    )
)
```

**STARTED → SENDING:**

The concrete strategy implementation drops credits. Example from a hypothetical fixed-rate strategy:

```python
async def _execute_single_phase(self, phase_stats: CreditPhaseStats) -> None:
    """Execute a single phase by dropping credits at a fixed rate."""
    while phase_stats.should_send():
        await self.credit_manager.drop_credit(
            credit_phase=phase_stats.type,
            credit_drop_ns=time.time_ns(),
        )
        phase_stats.sent += 1

        # Wait for the next credit drop time
        await asyncio.sleep(self.inter_request_delay_sec)
```

**SENDING → SENDING_COMPLETE:**

```python
phase_stats.sent_end_ns = time.time_ns()
self.execute_async(
    self.credit_manager.publish_phase_sending_complete(
        phase_config.type, phase_stats.sent_end_ns, phase_stats.sent
    )
)
```

**SENDING_COMPLETE → COMPLETE:**

Either naturally (all credits returned) or forced (timeout):

```python
# Natural completion
if is_phase_complete:
    phase_stats.end_ns = time.time_ns()
    self.execute_async(
        self.credit_manager.publish_phase_complete(
            message.phase, phase_stats.completed, phase_stats.end_ns
        )
    )
    self.phase_complete_event.set()

# Forced completion
async def _force_phase_completion(
    self, phase_stats: CreditPhaseStats, grace_period_timeout: bool = False
) -> None:
    if phase_stats.type in self.phase_stats:
        phase_stats.end_ns = time.time_ns()
        self.notice(f"Phase force-completed due to grace period timeout: {phase_stats}")

        self.execute_async(
            self.credit_manager.publish_phase_complete(
                phase_stats.type,
                phase_stats.completed,
                phase_stats.end_ns,
                timeout_triggered=True,
            )
        )

        self.phase_complete_event.set()

        if phase_stats.type == CreditPhase.PROFILING:
            await self.credit_manager.publish_credits_complete()
            self.all_phases_complete_event.set()

        self.phase_stats.pop(phase_stats.type)
```

## Semaphore Pattern

### Credit as Semaphore

The credit system implements a distributed semaphore pattern:

**Traditional Semaphore:**
```python
# Single-process semaphore
semaphore = asyncio.Semaphore(max_concurrency)

async with semaphore:
    await do_work()
```

**Credit-Based Semaphore:**
```python
# Distributed credit-based semaphore

# Timing Manager (semaphore controller)
await drop_credit(phase=CreditPhase.PROFILING)

# Worker (semaphore acquirer)
credit_msg = await receive_credit()
await do_work()
await return_credit(credit_msg.request_id)
```

### Benefits Over Traditional Semaphores

1. **Distributed**: Works across multiple processes and machines
2. **Precise Timing**: Credits can specify exact execution times
3. **Traceability**: Each credit has a unique ID for request tracing
4. **Flexible**: Supports different timing modes (rate-limited, concurrent, Poisson, etc.)
5. **Phase-Aware**: Different phases can have different concurrency/rate limits
6. **Graceful Shutdown**: Tracks in-flight requests and ensures clean completion

### Backpressure Management

The credit system provides natural backpressure:

```
Timing Manager                  Worker Pool
     │                               │
     ├─ drop_credit() ──────────────>│ Worker 1: BUSY
     │                               │
     ├─ drop_credit() ──────────────>│ Worker 2: BUSY
     │                               │
     ├─ drop_credit() ──────────────>│ Worker 3: BUSY
     │                               │
     ├─ drop_credit() ──────X        │ All workers busy!
     │                     (queued)  │ Credit queued in ZMQ
     │                               │
     │                               │ Worker 1: completes
     │ <────── return_credit() ──────┤
     │                               │
     │                               │ Worker 1: picks up queued credit
     │                      (dequeued)─────────────────────>
```

ZMQ's DEALER/ROUTER pattern ensures credits are distributed fairly to available workers.

## Rate Limiting Mechanisms

### Fixed Rate Limiting

For fixed-rate strategies, credits are dropped at regular intervals:

```python
async def _execute_single_phase(self, phase_stats: CreditPhaseStats) -> None:
    """Execute a fixed-rate phase."""
    interval_ns = NANOS_PER_SECOND / self.config.request_rate
    next_drop_ns = time.perf_counter_ns()

    while phase_stats.should_send():
        # Calculate next drop time
        next_drop_ns += interval_ns

        # Drop credit
        await self.credit_manager.drop_credit(
            credit_phase=phase_stats.type,
            credit_drop_ns=int(next_drop_ns),
        )
        phase_stats.sent += 1

        # Sleep until next drop time
        current_ns = time.perf_counter_ns()
        sleep_ns = next_drop_ns - current_ns
        if sleep_ns > 0:
            await asyncio.sleep(sleep_ns / NANOS_PER_SECOND)
```

### Concurrency-Based Rate Limiting

For concurrency strategies, credits are dropped as soon as previous ones return:

```python
async def _execute_single_phase(self, phase_stats: CreditPhaseStats) -> None:
    """Execute a concurrency-based phase."""
    # Initial burst up to max concurrency
    for _ in range(min(self.max_concurrency, phase_stats.total_expected_requests)):
        await self.credit_manager.drop_credit(
            credit_phase=phase_stats.type,
        )
        phase_stats.sent += 1

    # As credits return, drop new ones to maintain concurrency
    while phase_stats.should_send():
        # Wait for a credit to return
        await self._wait_for_credit_return()

        # Drop a new credit immediately
        await self.credit_manager.drop_credit(
            credit_phase=phase_stats.type,
        )
        phase_stats.sent += 1
```

### Poisson Distribution

For realistic load patterns, AIPerf supports Poisson-distributed arrivals:

```python
async def _execute_single_phase(self, phase_stats: CreditPhaseStats) -> None:
    """Execute a Poisson-distributed phase."""
    import random

    lambda_rate = self.config.request_rate  # Average rate

    while phase_stats.should_send():
        # Sample from exponential distribution (inter-arrival times)
        interval_sec = random.expovariate(lambda_rate)

        await asyncio.sleep(interval_sec)

        await self.credit_manager.drop_credit(
            credit_phase=phase_stats.type,
            credit_drop_ns=time.time_ns(),
        )
        phase_stats.sent += 1
```

## Request Cancellation

### Cancellation Strategy

AIPerf supports request cancellation for timeout testing. The `RequestCancellationStrategy` determines which requests should be cancelled:

```python
class RequestCancellationStrategy:
    """Strategy for determining which requests should be cancelled."""

    def __init__(self, config: TimingManagerConfig):
        self.config = config
        self.cancel_probability = config.cancel_probability
        self.cancel_after_ns = config.cancel_after_ns

    def should_cancel(self) -> bool:
        """Determine if a request should be cancelled."""
        if self.cancel_probability <= 0:
            return False
        return random.random() < self.cancel_probability

    def get_cancel_after_ns(self) -> int:
        """Get the cancellation delay in nanoseconds."""
        return self.cancel_after_ns
```

### Dropping Cancellable Credits

When dropping a credit that should be cancelled:

```python
should_cancel = self.cancellation_strategy.should_cancel()
cancel_after_ns = 0

if should_cancel:
    cancel_after_ns = self.cancellation_strategy.get_cancel_after_ns()

await self.credit_manager.drop_credit(
    credit_phase=phase_stats.type,
    credit_drop_ns=time.time_ns(),
    should_cancel=should_cancel,
    cancel_after_ns=cancel_after_ns,
)
```

### Worker-Side Cancellation

Workers receive the cancellation parameters and schedule the cancellation:

```python
async def process_credit(self, credit_msg: CreditDropMessage) -> None:
    """Process a credit drop message."""
    # Schedule cancellation if needed
    cancel_task = None
    if credit_msg.should_cancel:
        cancel_task = asyncio.create_task(
            self._cancel_after_delay(credit_msg.cancel_after_ns)
        )

    try:
        # Execute the request
        await self.send_request()
    except asyncio.CancelledError:
        # Request was cancelled
        self.record.was_cancelled = True
        self.record.cancellation_perf_ns = time.perf_counter_ns()
    finally:
        if cancel_task:
            cancel_task.cancel()

        # Return the credit
        await self.return_credit(credit_msg)

async def _cancel_after_delay(self, delay_ns: int) -> None:
    """Cancel the current task after a delay."""
    await asyncio.sleep(delay_ns / NANOS_PER_SECOND)
    # Cancel the request task
    self.current_task.cancel()
```

## Performance Implications

### Timing Precision

AIPerf uses nanosecond-precision timestamps for credit drops:

```python
credit_drop_ns = time.time_ns()  # Or time.perf_counter_ns()
```

**Why nanoseconds?**

1. **Sub-millisecond precision**: Modern inference can complete in microseconds
2. **Accurate rate limiting**: For high request rates (e.g., 1000 RPS), millisecond precision is insufficient
3. **Timing analysis**: Measuring inter-token latency or TTFT requires nanosecond precision

**Clock Selection:**

- `time.time_ns()`: Wall clock time, used for absolute timestamps
- `time.perf_counter_ns()`: Monotonic clock, used for latency measurements

### Memory Overhead

Each phase maintains a `CreditPhaseStats` object:

```python
phase_stats: dict[CreditPhase, CreditPhaseStats] = {}
```

**Memory per phase:**
- Phase config: ~100 bytes
- Stats: ~200 bytes
- Total: ~300 bytes per phase

With typically 1-2 phases (warmup + profiling), total memory overhead is negligible (<1 KB).

### Message Overhead

Each credit involves two messages:

1. `CreditDropMessage`: ~200 bytes
2. `CreditReturnMessage`: ~150 bytes

**Total per request:** ~350 bytes

For 10,000 requests: 3.5 MB of message overhead

**Mitigation strategies:**

- ZMQ compression (optional)
- Batch credit drops (for high-rate scenarios)
- Efficient serialization (msgpack/pickle)

### Concurrency Impact

The credit system enables controlled concurrency:

**Low concurrency (e.g., 10):**
- Pros: Predictable load, easy to reason about
- Cons: May not saturate the server

**High concurrency (e.g., 1000):**
- Pros: Saturates server, reveals bottlenecks
- Cons: Higher memory usage, more in-flight requests

**Optimal concurrency:**
- Start with 2x the number of CPU cores
- Adjust based on observed throughput and latency
- Monitor `in_flight` count to ensure it stays within limits

### Grace Period Tuning

The grace period affects measurement accuracy:

**Too short:**
- Requests that started just before duration expired may be cut off
- Reduces measured throughput
- May miss tail latencies

**Too long:**
- Includes requests that started after duration expired
- Inflates measured throughput
- May include outlier latencies

**Recommended:**
- Set to 2-3x the p99 request latency
- For typical inference: 5-10 seconds
- For long requests: 30-60 seconds

## Best Practices

### Credit Drop Timing

**Immediate drops (credit_drop_ns=None):**
```python
# Use for concurrency-based load
await self.credit_manager.drop_credit(
    credit_phase=CreditPhase.PROFILING,
    credit_drop_ns=None,  # Send ASAP
)
```

**Scheduled drops (credit_drop_ns=timestamp):**
```python
# Use for rate-limited or Poisson load
next_drop_ns = time.perf_counter_ns() + interval_ns
await self.credit_manager.drop_credit(
    credit_phase=CreditPhase.PROFILING,
    credit_drop_ns=next_drop_ns,  # Send at exact time
)
```

### Phase Configuration

**Count-based phases:**
- Use for warmup (fixed number of requests)
- Use for benchmarks with known request counts
- Ensures exact number of requests

**Time-based phases:**
- Use for sustained load testing
- Use for SLA validation (e.g., maintain 100 RPS for 60 seconds)
- Allows server to reach steady state

### Error Handling

**Credit drop failures:**
```python
try:
    await self.credit_manager.drop_credit(
        credit_phase=phase_stats.type,
        credit_drop_ns=time.time_ns(),
    )
    phase_stats.sent += 1
except Exception as e:
    self.error(f"Failed to drop credit: {e}")
    # Decide: retry, skip, or abort
```

**Credit return failures:**
```python
try:
    await self.return_credit(credit_msg)
except Exception as e:
    self.error(f"Failed to return credit: {e}")
    # This is critical - the Timing Manager won't know the request completed
    # Consider implementing a timeout-based cleanup mechanism
```

### Monitoring

**Track key metrics:**

```python
# In-flight requests
in_flight = phase_stats.sent - phase_stats.completed

# Progress percentage
progress = phase_stats.progress_percent

# Completion rate
if phase_stats.sent > 0:
    completion_rate = phase_stats.completed / phase_stats.sent
```

**Log important events:**

```python
# Phase transitions
self.info(f"Phase {phase} started: {phase_stats}")
self.info(f"Phase {phase} sending complete: sent={phase_stats.sent}")
self.notice(f"Phase {phase} completed: {phase_stats}")

# Anomalies
if phase_stats.in_flight > self.max_expected_concurrency * 2:
    self.warning(f"High in-flight count: {phase_stats.in_flight}")
```

## Common Patterns

### Warmup + Profiling

Standard benchmark pattern:

```python
# Warmup: 100 requests to prime caches
self.ordered_phase_configs.append(
    CreditPhaseConfig(
        type=CreditPhase.WARMUP,
        total_expected_requests=100,
    )
)

# Profiling: 60 seconds at target rate
self.ordered_phase_configs.append(
    CreditPhaseConfig(
        type=CreditPhase.PROFILING,
        expected_duration_sec=60,
    )
)
```

### Ramp-Up Load

Gradually increase load:

```python
async def _execute_single_phase(self, phase_stats: CreditPhaseStats) -> None:
    """Ramp up from min_rate to max_rate over duration."""
    start_rate = self.config.min_request_rate
    end_rate = self.config.max_request_rate
    duration_sec = phase_stats.expected_duration_sec

    start_ns = time.perf_counter_ns()

    while phase_stats.should_send():
        elapsed_sec = (time.perf_counter_ns() - start_ns) / NANOS_PER_SECOND
        progress = elapsed_sec / duration_sec

        # Linear ramp
        current_rate = start_rate + (end_rate - start_rate) * progress
        interval_sec = 1.0 / current_rate

        await self.credit_manager.drop_credit(
            credit_phase=phase_stats.type,
            credit_drop_ns=time.time_ns(),
        )
        phase_stats.sent += 1

        await asyncio.sleep(interval_sec)
```

### Burst Testing

Send credits in bursts:

```python
async def _execute_single_phase(self, phase_stats: CreditPhaseStats) -> None:
    """Send credits in bursts."""
    burst_size = self.config.burst_size
    burst_interval_sec = self.config.burst_interval_sec

    while phase_stats.should_send():
        # Send burst
        for _ in range(min(burst_size,
                           phase_stats.total_expected_requests - phase_stats.sent)):
            await self.credit_manager.drop_credit(
                credit_phase=phase_stats.type,
            )
            phase_stats.sent += 1

        # Wait before next burst
        await asyncio.sleep(burst_interval_sec)
```

## Troubleshooting

### Credits Not Returned

**Symptoms:**
- Phase never completes
- `in_flight` count keeps growing
- No `CreditReturnMessage` received

**Causes:**
1. Worker crashed without returning credit
2. Network partition
3. ZMQ socket closed prematurely

**Solutions:**
- Implement credit return timeout
- Add worker health checks
- Enable ZMQ heartbeats

### Timing Drift

**Symptoms:**
- Actual rate differs from target rate
- Credits delayed more than expected

**Causes:**
1. System clock drift
2. High CPU load
3. Asyncio event loop saturation

**Solutions:**
- Use monotonic clock (`perf_counter_ns`)
- Reduce credit drop rate
- Scale out to multiple Timing Manager instances

### Phase Hangs

**Symptoms:**
- Phase stuck in SENDING_COMPLETE state
- Waiting indefinitely for completion

**Causes:**
1. Miscounted credits (sent != completed + in_flight)
2. Lost credit return messages
3. Worker still processing

**Solutions:**
- Enable forced phase completion after timeout
- Add detailed logging of credit lifecycle
- Implement credit reconciliation

## Key Takeaways

1. **Credit System Design**: AIPerf uses a credit-based semaphore pattern for distributed flow control, enabling precise timing and backpressure management.

2. **Phase-Based Execution**: Benchmarks consist of sequential phases (warmup, profiling) with distinct configurations and completion criteria.

3. **Flexible Timing Modes**: Phases can be count-based (fixed number of requests) or time-based (fixed duration), supporting various testing scenarios.

4. **Message-Driven**: Credits are implemented as messages (CreditDropMessage, CreditReturnMessage) flowing through ZMQ, enabling distributed coordination.

5. **Graceful Completion**: The system tracks in-flight requests and implements grace periods to ensure all work completes before phase transitions.

6. **Nanosecond Precision**: All timing uses nanosecond-resolution timestamps for accurate rate limiting and latency measurement.

7. **Extensible Strategy Pattern**: The abstract CreditIssuingStrategy enables different load patterns (fixed rate, concurrency, Poisson, etc.) via subclassing.

8. **Request Cancellation**: Built-in support for cancelling requests after a delay, enabling timeout and cancellation testing.

9. **Progress Tracking**: Real-time progress reporting via CreditPhaseProgressMessage enables live monitoring and UI updates.

10. **Performance Considerations**: Low memory overhead, but message overhead scales with request count; timing precision critical for high-rate scenarios.

Next: [Chapter 12: Records Manager](chapter-12-records-manager.md)

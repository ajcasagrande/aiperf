# Chapter 10: Timing Manager

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Table of Contents
- [Timing Manager Role](#timing-manager-role)
- [Credit Issuing Strategies](#credit-issuing-strategies)
- [Phase Management](#phase-management)
- [Scheduling Algorithms](#scheduling-algorithms)
- [Implementation Details](#implementation-details)
- [Key Takeaways](#key-takeaways)

## Timing Manager Role

The Timing Manager (`/home/anthony/nvidia/projects/aiperf/aiperf/timing/timing_manager.py`) is responsible for controlling when requests are executed by issuing timing credits to workers.

### Primary Responsibilities

1. **Credit Issuance**: Issue credits according to load generation strategy
2. **Phase Management**: Coordinate warmup and profiling phases
3. **Credit Tracking**: Track issued and returned credits
4. **Rate Control**: Implement precise request rate control
5. **Schedule Execution**: Support deterministic trace replay

### Initialization

```python
@ServiceFactory.register(ServiceType.TIMING_MANAGER)
class TimingManager(
    PullClientMixin,
    BaseComponentService,
    CreditPhaseMessagesMixin
):
    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str | None = None,
    ) -> None:
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
            pull_client_address=CommAddress.CREDIT_RETURN,
            pull_client_bind=True,
        )

        self.config = TimingManagerConfig.from_user_config(self.user_config)

        # ZMQ clients
        self.dataset_request_client = self.comms.create_request_client(
            CommAddress.DATASET_MANAGER_PROXY_FRONTEND,
        )
        self.credit_drop_push_client = self.comms.create_push_client(
            CommAddress.CREDIT_DROP,
            bind=True,
        )

        self._credit_issuing_strategy: CreditIssuingStrategy | None = None
```

## Credit Issuing Strategies

### Strategy Selection

```python
@on_command(CommandType.PROFILE_CONFIGURE)
async def _profile_configure_command(
    self, message: ProfileConfigureCommand
) -> None:
    """Configure the timing manager."""

    if self.config.timing_mode == TimingMode.FIXED_SCHEDULE:
        # Request timing data from Dataset Manager
        dataset_timing_response = (
            await self.dataset_request_client.request(
                DatasetTimingRequest(service_id=self.service_id)
            )
        )

        self._credit_issuing_strategy = (
            CreditIssuingStrategyFactory.create_instance(
                TimingMode.FIXED_SCHEDULE,
                config=self.config,
                credit_manager=self,
                schedule=dataset_timing_response.timing_data,
            )
        )
    else:
        # Concurrency or request rate mode
        self._credit_issuing_strategy = (
            CreditIssuingStrategyFactory.create_instance(
                self.config.timing_mode,
                config=self.config,
                credit_manager=self,
            )
        )
```

### Base Strategy

```python
class CreditIssuingStrategy(TaskManagerMixin, ABC):
    def __init__(
        self,
        config: TimingManagerConfig,
        credit_manager: CreditManagerProtocol
    ):
        self.config = config
        self.credit_manager = credit_manager
        self.cancellation_strategy = RequestCancellationStrategy(config)

        # Phase tracking
        self.all_phases_complete_event = asyncio.Event()
        self.phase_complete_event = asyncio.Event()
        self.phase_stats: dict[CreditPhase, CreditPhaseStats] = {}
        self.ordered_phase_configs: list[CreditPhaseConfig] = []

        self._setup_phase_configs()
        self._validate_phase_configs()

    @abstractmethod
    async def _execute_single_phase(
        self, phase_stats: CreditPhaseStats
    ) -> None:
        """Execute a single phase. Must be implemented by subclasses."""
        raise NotImplementedError
```

### Concurrency Strategy

Maintains fixed number of concurrent requests:

```python
class ConcurrencyStrategy(CreditIssuingStrategy):
    async def _execute_single_phase(
        self, phase_stats: CreditPhaseStats
    ) -> None:
        """Execute phase with fixed concurrency."""
        target_requests = phase_stats.expected_requests

        # Issue initial burst of credits up to concurrency
        for _ in range(self.config.concurrency):
            if phase_stats.sent >= target_requests:
                break
            await self._issue_credit(phase_stats)

        # Issue more credits as they return
        while phase_stats.sent < target_requests:
            # Wait for credit return
            # (handled by _on_credit_return callback)
            await asyncio.sleep(0.01)

            # Issue replacement credit
            if phase_stats.sent < target_requests:
                await self._issue_credit(phase_stats)

        phase_stats.sent_end_ns = time.time_ns()
```

### Request Rate Strategy

Issues credits at specific rate:

```python
class RequestRateStrategy(CreditIssuingStrategy):
    async def _execute_single_phase(
        self, phase_stats: CreditPhaseStats
    ) -> None:
        """Execute phase with request rate control."""
        if phase_stats.is_time_based:
            # Time-based: issue until duration elapsed
            await self._execute_time_based_phase(phase_stats)
        else:
            # Count-based: issue exact number
            await self._execute_count_based_phase(phase_stats)

    async def _execute_count_based_phase(
        self, phase_stats: CreditPhaseStats
    ) -> None:
        target_requests = phase_stats.expected_requests
        interval_s = 1.0 / self.config.request_rate

        for i in range(target_requests):
            # Issue credit
            await self._issue_credit(phase_stats)

            # Wait for interval (if not last)
            if i < target_requests - 1:
                if self.config.request_rate_mode == TimingMode.POISSON:
                    # Poisson distribution
                    wait_time = random.expovariate(self.config.request_rate)
                else:
                    # Constant rate
                    wait_time = interval_s

                await asyncio.sleep(wait_time)

        phase_stats.sent_end_ns = time.time_ns()
```

### Fixed Schedule Strategy

Issues credits at predetermined times:

```python
class FixedScheduleStrategy(CreditIssuingStrategy):
    def __init__(
        self,
        config: TimingManagerConfig,
        credit_manager: CreditManagerProtocol,
        schedule: list[tuple[int, str]],  # (timestamp_ms, conversation_id)
    ):
        super().__init__(config, credit_manager)
        self.schedule = schedule

    async def _execute_single_phase(
        self, phase_stats: CreditPhaseStats
    ) -> None:
        """Execute phase with fixed schedule."""
        start_time = time.time()

        for timestamp_ms, conversation_id in self.schedule:
            # Calculate target time
            target_time = start_time + (timestamp_ms / 1000.0)

            # Wait until target time
            now = time.time()
            if target_time > now:
                await asyncio.sleep(target_time - now)

            # Issue credit with specific conversation
            await self._issue_credit(
                phase_stats,
                conversation_id=conversation_id
            )

        phase_stats.sent_end_ns = time.time_ns()
```

## Phase Management

### Phase Configuration

```python
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
        # Time-based
        self.ordered_phase_configs.append(
            CreditPhaseConfig(
                type=CreditPhase.PROFILING,
                expected_duration_sec=self.config.benchmark_duration,
            )
        )
    else:
        # Count-based
        self.ordered_phase_configs.append(
            CreditPhaseConfig(
                type=CreditPhase.PROFILING,
                total_expected_requests=self.config.request_count,
            )
        )
```

### Phase Execution

```python
async def _execute_phases(self) -> None:
    """Execute all credit phases sequentially."""
    for phase_config in self.ordered_phase_configs:
        self.phase_complete_event.clear()

        # Create phase stats
        phase_stats = CreditPhaseStats.from_phase_config(phase_config)
        phase_stats.start_ns = time.time_ns()
        self.phase_stats[phase_config.type] = phase_stats

        # Announce phase start
        self.execute_async(
            self.credit_manager.publish_phase_start(
                phase_config.type,
                phase_stats.start_ns,
                phase_config.total_expected_requests,
                phase_config.expected_duration_sec,
            )
        )

        # Execute phase (strategy-specific)
        await self._execute_single_phase(phase_stats)

        # Announce sending complete
        phase_stats.sent_end_ns = time.time_ns()
        self.execute_async(
            self.credit_manager.publish_phase_sending_complete(
                phase_config.type,
                phase_stats.sent_end_ns,
                phase_stats.sent
            )
        )

        # Wait for all credits to return
        await self._wait_for_phase_completion(phase_stats)
```

### Phase Completion

```python
async def _wait_for_phase_completion(
    self, phase_stats: CreditPhaseStats
) -> None:
    """Wait for a phase to complete."""
    if phase_stats.is_time_based:
        # Time-based: wait with timeout
        elapsed_ns = time.time_ns() - phase_stats.start_ns
        elapsed_sec = elapsed_ns / NANOS_PER_SECOND
        remaining_sec = max(0, phase_stats.expected_duration_sec - elapsed_sec)
        grace_period = self.config.benchmark_grace_period
        total_timeout = remaining_sec + grace_period

        try:
            await asyncio.wait_for(
                self.phase_complete_event.wait(),
                timeout=total_timeout
            )
        except asyncio.TimeoutError:
            # Force completion
            await self._force_phase_completion(phase_stats, grace_period_timeout=True)
    else:
        # Count-based: wait indefinitely
        await self.phase_complete_event.wait()
```

## Scheduling Algorithms

### Credit Return Tracking

```python
@on_pull_message(MessageType.CREDIT_RETURN)
async def _on_credit_return(self, message: CreditReturnMessage) -> None:
    """Handle credit return message."""
    if self._credit_issuing_strategy:
        await self._credit_issuing_strategy._on_credit_return(message)

# In strategy:
async def _on_credit_return(self, message: CreditReturnMessage) -> None:
    """Track credit returns."""
    if message.phase not in self.phase_stats:
        return

    phase_stats = self.phase_stats[message.phase]
    phase_stats.completed += 1

    # Check if phase is complete
    if phase_stats.is_sending_complete:
        if phase_stats.is_request_count_based:
            # Count-based: complete when all returned
            if phase_stats.completed >= phase_stats.sent:
                await self._complete_phase(phase_stats)
        else:
            # Time-based: complete when all returned within grace period
            if phase_stats.in_flight == 0:
                await self._complete_phase(phase_stats)
```

### Progress Reporting

```python
async def _progress_report_loop(self) -> None:
    """Report progress periodically."""
    while not self.all_phases_complete_event.is_set():
        for phase_type, phase_stats in self.phase_stats.items():
            self.debug(
                f"Phase {phase_type}: "
                f"sent={phase_stats.sent}, "
                f"completed={phase_stats.completed}, "
                f"in_flight={phase_stats.in_flight}"
            )
        await asyncio.sleep(DEFAULT_CREDIT_PROGRESS_REPORT_INTERVAL)
```

## Implementation Details

### Credit Drop

```python
async def drop_credit(
    self,
    credit_phase: CreditPhase,
    conversation_id: str | None = None,
    credit_drop_ns: int | None = None,
    should_cancel: bool = False,
    cancel_after_ns: int = 0,
) -> None:
    """Drop a credit."""
    self.execute_async(
        self.credit_drop_push_client.push(
            message=CreditDropMessage(
                service_id=self.service_id,
                phase=credit_phase,
                credit_drop_ns=credit_drop_ns,
                conversation_id=conversation_id,
                should_cancel=should_cancel,
                cancel_after_ns=cancel_after_ns,
            ),
        )
    )
```

### Request Cancellation

```python
class RequestCancellationStrategy:
    def __init__(self, config: TimingManagerConfig):
        self.cancellation_rate = config.request_cancellation_rate
        self.cancellation_delay_ns = int(
            config.request_cancellation_delay * NANOS_PER_SECOND
        )

    def should_cancel_request(self) -> bool:
        """Determine if this request should be cancelled."""
        return random.random() < self.cancellation_rate

    def get_cancellation_delay_ns(self) -> int:
        """Get cancellation delay for this request."""
        return self.cancellation_delay_ns
```

### Phase Stats

```python
class CreditPhaseStats:
    type: CreditPhase
    start_ns: int
    sent_end_ns: int | None
    end_ns: int | None
    sent: int = 0
    completed: int = 0
    expected_requests: int | None
    expected_duration_sec: float | None

    @property
    def in_flight(self) -> int:
        return self.sent - self.completed

    @property
    def is_sending_complete(self) -> bool:
        return self.sent_end_ns is not None

    @property
    def is_time_based(self) -> bool:
        return self.expected_duration_sec is not None

    @property
    def is_request_count_based(self) -> bool:
        return self.expected_requests is not None
```

## Key Takeaways

1. **Strategy Pattern**: Credit issuing uses strategy pattern for different load generation modes.

2. **Phase-Based Execution**: Separates warmup and profiling with proper phase management.

3. **Credit Tracking**: Precisely tracks issued and returned credits for accurate control.

4. **Multiple Modes**: Supports concurrency, request rate, and fixed schedule modes.

5. **Time-Based Support**: Can run for specific durations with grace periods.

6. **Request Cancellation**: Supports probabilistic request cancellation for SLA testing.

7. **Progress Reporting**: Provides periodic progress updates for monitoring.

8. **Completion Detection**: Properly detects phase completion for both count and time-based modes.

9. **Schedule Replay**: Supports deterministic trace replay with precise timing.

10. **Async Control**: Uses asyncio for precise, non-blocking timing control.

The Timing Manager is the conductor of the AIPerf orchestra, precisely controlling when each request executes to achieve the desired load pattern while maintaining accurate measurement.

---

**Congratulations!** You've completed all 10 chapters of the AIPerf Developer's Guidebook covering Foundation and Core Systems. You now have a comprehensive understanding of AIPerf's architecture, components, and implementation details.

### Where to Go Next

- **Advanced Features**: Explore request cancellation, trace replay, and custom metrics
- **Extension Development**: Create custom endpoint types, metrics, or exporters
- **Performance Tuning**: Optimize AIPerf for your specific use cases
- **Contribution**: Contribute back to the AIPerf project

### Additional Resources

- **Official Documentation**: `/home/anthony/nvidia/projects/aiperf/docs/`
- **Source Code**: `/home/anthony/nvidia/projects/aiperf/aiperf/`
- **GitHub**: https://github.com/ai-dynamo/aiperf
- **Discord**: https://discord.gg/D92uqZRjCZ

Happy benchmarking!

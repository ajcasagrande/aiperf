<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# End-to-End Solution for Ramp-up vs Steady-State Metrics

## Problem Statement

The AI performance benchmarking system was calculating metrics incorrectly during ramp-up phases. Previously, all metrics (requests per second, processing rates, ETA) were calculated from the start of the phase, which included ramp-up time. This gave inaccurate steady-state performance measurements.

## Solution Overview

This solution implements proper timing differentiation between ramp-up and steady-state phases throughout the entire codebase:

### 1. Infrastructure Already in Place

- **ProfileProgressMessage**: Already had both `start_ns` and `measurement_start_ns` fields
- **CreditPhase**: Already had both `start_time_ns` and `measurement_start_time_ns` fields
- **TimingManager**: Already properly publishes both timing fields

### 2. Updated Components

#### A. Timing Strategies

**RequestRateStrategy** (`aiperf/services/timing_manager/request_rate_strategy.py`):
- Now sets `phase.measurement_start_time_ns = phase.start_time_ns` (no ramp-up in rate mode)
- Updated debug logging to use measurement start time for rate calculations

**ConcurrencyStrategy** (`aiperf/services/timing_manager/concurrency_strategy.py`):
- Already properly sets `phase.measurement_start_time_ns` after ramp-up completion
- Updated debug logging to use measurement start time for rate calculations
- In burst mode: `phase.measurement_start_time_ns = phase.start_time_ns`
- In ramp-up mode: `phase.measurement_start_time_ns = time.time_ns()` (set after ramp-up)

**FixedScheduleStrategy** (`aiperf/services/timing_manager/fixed_schedule_strategy.py`):
- Refactored to use proper `CreditPhase` model for progress tracking
- Sets `phase.measurement_start_time_ns = phase.start_time_ns` (no ramp-up in fixed mode)
- Added progress reporting and credit return handling

#### B. Progress Tracking

**ProgressTracker** (`aiperf/progress/progress_tracker.py`):
- `update_profile_progress()`: Now uses `measurement_start_ns` for steady-state metrics
- `update_processing_stats()`: Uses stored measurement start time for processing rates
- Stores measurement start time in profile for cross-method access
- Falls back to `start_ns` when `measurement_start_ns` is 0 or None

### 3. Key Changes Made

#### Metrics Calculation Logic:
```python
# OLD (incorrect):
requests_per_second = completed / (current_time - start_time)

# NEW (correct):
measurement_start_ns = message.measurement_start_ns if message.measurement_start_ns > 0 else message.start_ns
requests_per_second = completed / (current_time - measurement_start_ns)
```

#### Timing Differentiation:
- **Overall elapsed time**: Uses `start_ns` (includes ramp-up time)
- **Steady-state metrics**: Uses `measurement_start_ns` (excludes ramp-up time)
- **ETA calculations**: Uses steady-state rates for accurate predictions

### 4. Ramp-up Behavior by Strategy

1. **ConcurrencyStrategy with ramp-up**:
   - `start_time_ns`: Set when phase begins
   - `measurement_start_time_ns`: Set after ramp-up completes
   - Result: Metrics exclude ramp-up requests

2. **RequestRateStrategy**:
   - `start_time_ns`: Set when phase begins
   - `measurement_start_time_ns`: Set to same value (no ramp-up)
   - Result: Metrics include all requests

3. **FixedScheduleStrategy**:
   - `start_time_ns`: Set when phase begins
   - `measurement_start_time_ns`: Set to same value (no ramp-up)
   - Result: Metrics include all requests

### 5. Verification

Added comprehensive tests in `test_progress_tracker.py`:
- `test_measurement_start_time_ns_usage()`: Verifies correct timing usage
- `test_measurement_start_time_ns_fallback()`: Verifies fallback behavior

### 6. Backward Compatibility

- Falls back to `start_ns` when `measurement_start_ns` is 0 or None
- All existing functionality remains unchanged
- UI and other consumers automatically benefit from improved metrics

## Result

The system now provides accurate steady-state performance metrics while maintaining proper overall timing information. Users get correct requests/second calculations that exclude ramp-up distortions, leading to more accurate performance assessments.

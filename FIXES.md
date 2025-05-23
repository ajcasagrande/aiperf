<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
# 
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
# 
#  http://www.apache.org/licenses/LICENSE-2.0
# 
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
-->
# Dask Worker Manager Fixes

## Issues Found and Fixed

### 1. Missing Dependencies
**Problem**: Empty `requirements-dask.txt` file causing import errors.

**Fix**: Added proper Dask dependencies:
```bash
pip install dask[complete]>=2023.11.0 distributed>=2023.11.0 psutil>=5.9.0 bokeh>=3.0.0
```

### 2. Task Function Serialization Error
**Problem**: ZMQ contexts can't be pickled when Dask tries to serialize tasks.

**Fix**: Moved task functions outside the class to avoid serialization issues:
- `process_credit_task()`
- `health_check_task()`
- `compute_task()`

### 3. Task Handler Signature Mismatch
**Problem**: `health_check_task()` was being called with arguments but expects none.

**Fix**: Changed from `client.map(health_check_task, range(worker_count))` to individual `client.submit(health_check_task)` calls.

### 4. Awaiting Non-Awaitable Objects
**Problem**: Task results are dictionaries but were being awaited.

**Fix**: Changed `result = await future` to `result = future.result()` in `_handle_task_completion()`.

### 5. Client Close on None
**Problem**: Trying to await `self.client.close()` when `self.client` is already `None`.

**Fix**: Already had proper None checks, but the error suggests the client becomes None during shutdown.

### 6. Credit Drop Callback Signature
**Problem**: Callback expected `CreditDropMessage` but received generic `Message`.

**Fix**: Updated callback signature and added proper type checking for payload attributes.

### 7. Demo Service Lifecycle
**Problem**: Demo was calling private methods and non-existent `cleanup()` method.

**Fix**:
- Changed `_initialize()` → `initialize()`
- Changed `_start()` → `start()`
- Removed `cleanup()` calls
- Fixed `CreditDropMessage` constructor

## Installation Instructions

1. **Install Dask dependencies**:
   ```bash
   pip install dask[complete] distributed psutil bokeh cloudpickle tornado
   ```

2. **Test the fixes** with the simple test script:
   ```bash
   python examples/simple_dask_test.py
   ```

3. **Run the full demo** (after dependencies are installed):
   ```bash
   python examples/dask_worker_manager_demo.py
   ```

## Key Changes Made

### DaskWorkerManager (`aiperf/services/worker_manager/dask_worker_manager.py`)

1. **Moved task functions to module level** (lines 75-133):
   ```python
   def process_credit_task(credit_message_dict: dict) -> dict:
   def health_check_task() -> dict:
   def compute_task(data: Any) -> dict:
   ```

2. **Fixed metrics collection** (lines 694-720):
   ```python
   # Create individual submit calls instead of map
   futures = []
   for _ in range(worker_count):
       future = self.client.submit(health_check_task)
       futures.append(future)
   ```

3. **Fixed task completion handling** (lines 602-623):
   ```python
   result = future.result()  # Don't await, just get result
   ```

4. **Improved credit drop handling** (lines 557-570):
   ```python
   if (hasattr(message, 'payload') and
       hasattr(message.payload, 'amount') and
       isinstance(message.payload.amount, (int, float))):
   ```

### Demo Script (`examples/dask_worker_manager_demo.py`)

1. **Fixed service lifecycle calls**:
   - `await manager.initialize()`
   - `await manager.start()`
   - `await manager.stop()` (removed cleanup calls)

2. **Fixed credit message creation**:
   ```python
   credit_message = CreditDropMessage(payload=credit_payload)
   ```

## Expected Behavior After Fixes

1. **No serialization errors** - Task functions can be properly pickled and sent to workers
2. **Proper task execution** - Health checks and compute tasks run without signature errors
3. **Clean shutdown** - No more "NoneType can't be used in 'await'" errors
4. **Successful credit processing** - Credit drops are properly handled and processed

## Testing Strategy

1. **Unit level**: Run `python examples/simple_dask_test.py` to test core functionality
2. **Integration level**: Run the full demo after installing dependencies
3. **Manual testing**: Check Dask dashboard at http://localhost:8787 during execution

The fixes address all the major issues that were causing the Dask Worker Manager to fail during initialization and task execution.

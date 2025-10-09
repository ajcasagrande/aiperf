<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Dataset Chunking: Reproducibility Fix

## Problem Statement

The initial chunking implementation used round-robin distribution which **breaks reproducibility**:
- Ignores the random seed
- Different worker patterns → different conversation distribution
- Cannot reproduce benchmarks with same seed

## Root Cause

```python
# WRONG: Round-robin ignores random seed
def _get_conversation_chunk(self, size: int):
    for _ in range(size):
        session_id = self._session_ids_cache[self._chunk_cursor]
        conversations.append(self.dataset[session_id])
        self._chunk_cursor = (self._chunk_cursor + 1) % len(self._session_ids_cache)
```

## Correct Solution: Two Strategies

### Strategy 1: Use Seeded Random (For Random Mode)

**Maintain the exact same random sequence as single-conversation mode:**

```python
def _get_conversation_chunk(self, size: int) -> list[Conversation]:
    """Get chunk while maintaining random sequence reproducibility."""
    conversations = []

    for _ in range(size):
        if self._use_sequential_iteration:
            # Sequential mode: deterministic index-based
            session_id = self._session_ids_cache[self._sequential_iterator_index]
            self._sequential_iterator_index = (
                self._sequential_iterator_index + 1
            ) % len(self._session_ids_cache)
        else:
            # Random mode: use seeded random (CRITICAL for reproducibility!)
            session_id = self._conversation_query_random.choice(
                self._session_ids_cache
            )

        conversations.append(self.dataset[session_id])

    return conversations
```

**Why this works:**
- Uses the same `self._conversation_query_random` with seed
- Each `choice()` call advances the random state identically
- 100 conversations in chunk = 100 calls to `choice()` = same as 100 single requests
- Request/reply is synchronous, so order is deterministic

**Reproducibility guarantee:**
```python
# Run 1: Seed=42, 1000 workers request 10 chunks each
# Chunk 1: conversations [5, 23, 67, 12, ...]  # from random sequence
# Chunk 2: conversations [89, 3, 45, 91, ...]  # next in random sequence

# Run 2: Seed=42, 1000 workers request 10 chunks each
# Chunk 1: conversations [5, 23, 67, 12, ...]  # IDENTICAL
# Chunk 2: conversations [89, 3, 45, 91, ...]  # IDENTICAL
```

### Strategy 2: Pre-Shuffle Once (Alternative)

**For even stronger guarantees, pre-shuffle the entire list:**

```python
async def _configure_dataset(self) -> None:
    # ... existing dataset loading ...

    self.dataset = {conv.session_id: conv for conv in conversations}
    self._session_ids_cache = list(self.dataset.keys())

    # NEW: Pre-shuffle list once with seed for reproducibility
    if not self._use_sequential_iteration:
        # Create temporary random instance for shuffling
        shuffle_random = random.Random(self.user_config.input.random_seed)
        shuffle_random.shuffle(self._session_ids_cache)
        self.info(f"Pre-shuffled dataset with seed {self.user_config.input.random_seed}")

    # Reset cursors
    self._chunk_cursor = 0
    self._chunk_counter = 0

    self.dataset_configured.set()
```

Then use simple round-robin on the pre-shuffled list:

```python
def _get_conversation_chunk(self, size: int) -> list[Conversation]:
    """Get chunk from pre-shuffled list (deterministic order)."""
    conversations = []

    for _ in range(size):
        session_id = self._session_ids_cache[self._chunk_cursor]
        conversations.append(self.dataset[session_id])
        self._chunk_cursor = (self._chunk_cursor + 1) % len(self._session_ids_cache)

    return conversations
```

**Why this works:**
- List is shuffled ONCE with seed at configuration time
- All subsequent chunk requests are deterministic
- Worker request timing doesn't matter
- Even simpler logic

**Trade-off:**
- ✅ Stronger reproducibility (order is fixed)
- ✅ Simpler chunk logic
- ⚠️ Different randomness behavior than current (shuffle vs repeated sampling)

## Recommended Solution: Strategy 1

**Use Strategy 1 (Seeded Random)** because:
1. **Identical behavior** to single-conversation mode
2. **Perfect backwards compatibility**
3. **Same random distribution** (sampling with replacement)
4. **No change to randomness semantics**

## Updated Implementation

### Updated DatasetManager Method

```python
def _get_conversation_chunk(self, size: int) -> list[Conversation]:
    """Get a chunk of conversations maintaining reproducibility.

    Uses the seeded random generator to maintain the exact same
    random sequence as single-conversation mode, ensuring benchmarks
    are reproducible with the same random seed.

    For sequential iteration mode, uses index-based iteration.

    Args:
        size: Number of conversations to return

    Returns:
        List of Conversation objects in reproducible order
    """
    if not self._session_ids_cache:
        return []

    conversations = []

    for _ in range(size):
        if self._use_sequential_iteration:
            # Sequential mode: deterministic index-based iteration
            if self._sequential_iterator_index >= len(self._session_ids_cache):
                # Reset iterator if we've gone through all conversations
                self._sequential_iterator_index = 0

            session_id = self._session_ids_cache[self._sequential_iterator_index]
            self._sequential_iterator_index += 1
        else:
            # Random mode: use seeded random generator
            # This maintains the exact same random sequence as single-conversation mode
            session_id = self._conversation_query_random.choice(
                self._session_ids_cache
            )

        conversations.append(self.dataset[session_id])

    return conversations
```

### Remove Old Round-Robin Code

**DELETE these lines from `__init__`:**
```python
# DELETE: No longer needed with seeded random approach
# self._chunk_cursor = 0
```

**DELETE from `_configure_dataset`:**
```python
# DELETE: No longer needed
# self._chunk_cursor = 0
```

## Verification

### Test 1: Same Seed, Same Results

```python
async def test_chunking_reproducibility():
    """Verify same seed produces same conversation order."""

    # Run 1
    config1 = UserConfig(input=InputConfig(random_seed=42))
    dm1 = DatasetManager(config1, ServiceConfig())
    await dm1._configure_dataset()

    chunk1_run1 = dm1._get_conversation_chunk(100)
    chunk2_run1 = dm1._get_conversation_chunk(100)

    # Run 2 with same seed
    config2 = UserConfig(input=InputConfig(random_seed=42))
    dm2 = DatasetManager(config2, ServiceConfig())
    await dm2._configure_dataset()

    chunk1_run2 = dm2._get_conversation_chunk(100)
    chunk2_run2 = dm2._get_conversation_chunk(100)

    # MUST be identical
    assert chunk1_run1 == chunk1_run2
    assert chunk2_run1 == chunk2_run2
```

### Test 2: Matches Single-Conversation Mode

```python
async def test_chunking_matches_single_mode():
    """Verify chunking gives same sequence as single-conversation mode."""

    # Single-conversation mode
    config1 = UserConfig(input=InputConfig(random_seed=42))
    dm1 = DatasetManager(config1, ServiceConfig())
    await dm1._configure_dataset()

    single_convos = []
    for _ in range(100):
        single_convos.append(dm1._return_any_conversation(None).conversation)

    # Chunking mode
    config2 = UserConfig(input=InputConfig(random_seed=42))
    dm2 = DatasetManager(config2, ServiceConfig())
    await dm2._configure_dataset()

    chunk_convos = dm2._get_conversation_chunk(100)

    # MUST be identical sequence
    assert single_convos == chunk_convos
```

### Test 3: Sequential Mode Reproducibility

```python
async def test_sequential_chunking_reproducibility():
    """Verify sequential mode maintains order."""

    config = UserConfig(input=InputConfig(custom_dataset_type=CustomDatasetType.MOONCAKE_TRACE))
    dm = DatasetManager(config, ServiceConfig())
    await dm._configure_dataset()

    # Get chunks
    chunk1 = dm._get_conversation_chunk(50)
    chunk2 = dm._get_conversation_chunk(50)
    chunk3 = dm._get_conversation_chunk(50)

    # Should be sequential in order
    all_ids = [c.session_id for c in chunk1 + chunk2 + chunk3]
    expected_ids = dm._session_ids_cache[:150]

    assert all_ids == expected_ids
```

## Impact on Performance

**No performance impact!** The seeded random approach:
- ✅ Still 100x fewer requests
- ✅ Still chunks 100 conversations per request
- ✅ Still reduces network overhead
- ✅ Random.choice() is O(1) - negligible cost

## Documentation Update

### User-Facing Guarantee

**Add to documentation:**

> **Reproducibility Guarantee**: AIPerf ensures that benchmarks run with the same
> random seed will produce identical results, regardless of whether chunking is
> enabled or disabled. The chunking optimization maintains the exact same random
> sequence as single-conversation mode, ensuring scientific reproducibility of
> benchmark results.

### Configuration Note

```bash
# These produce IDENTICAL conversation sequences:
aiperf profile --random-seed=42 --enable-chunking=false ...
aiperf profile --random-seed=42 --enable-chunking=true ...
```

## Summary of Changes

### Files to Update

1. **`aiperf/dataset/dataset_manager.py`**:
   - ✅ Remove `_chunk_cursor` initialization
   - ✅ Update `_get_conversation_chunk()` to use seeded random
   - ✅ Remove cursor advancement in `_configure_dataset()`

2. **Tests to add**:
   - `test_chunking_reproducibility()`
   - `test_chunking_matches_single_mode()`
   - `test_sequential_chunking_reproducibility()`

### Lines Changed

- **Remove**: ~5 lines (chunk_cursor references)
- **Update**: ~20 lines (new _get_conversation_chunk logic)
- **Add tests**: ~80 lines

**Net change**: ~100 lines for complete reproducibility guarantee

## Conclusion

By using the **seeded random generator** instead of round-robin, we maintain:

✅ **Perfect reproducibility** - same seed = same results
✅ **Backwards compatibility** - identical to single-conversation mode
✅ **Scientific validity** - benchmarks can be reproduced
✅ **Performance** - still 100x faster
✅ **Simplicity** - cleaner code (no cursor tracking)

This is the correct solution that respects AIPerf's reproducibility requirements.

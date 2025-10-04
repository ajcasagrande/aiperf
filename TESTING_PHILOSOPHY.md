<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Testing Philosophy

## Core Principle

**Test outcomes and behavior, not implementation details.**

Every test should answer: "What bug would this catch?"

If you cannot clearly articulate what real-world failure this test prevents, the test may not be valuable.

## What to Test

### Test Behavioral Guarantees

```python
# GOOD: Tests critical guarantee
def test_credit_returned_even_on_error():
    """Credit must be returned even if processing fails.

    Bug prevented: Lost credits that halt benchmark.
    """
    # Simulate error during processing
    with patch.object(worker, 'process', side_effect=Exception):
        await worker.handle_credit(credit)

    # Verify credit was still returned
    assert worker.returned_credits == 1
```

```python
# BAD: Tests Python behavior
def test_exception_is_raised():
    """Test that exceptions are raised."""
    with pytest.raises(Exception):
        raise Exception("test")
```

### Test Integration Points

```python
# GOOD: Tests service integration
def test_worker_retrieves_conversation_from_dataset_manager():
    """Worker must correctly request and receive conversation data.

    Bug prevented: Wrong message format causes request failure.
    """
    response = await worker.request_conversation(conv_id)
    assert response.conversation.session_id == conv_id
```

```python
# BAD: Tests Pydantic validation
def test_config_validates_positive_number():
    """Test that config rejects negative numbers."""
    with pytest.raises(ValidationError):
        Config(value=-1)
```

**Why**: Pydantic already tests its validation. We don't need to re-test it.

### Test Edge Cases That Matter

```python
# GOOD: Tests critical boundary
def test_grace_period_includes_requests_at_boundary():
    """Requests at exactly grace period cutoff should be included.

    Bug prevented: Off-by-one error excludes valid requests.
    """
    request_at_cutoff = create_request(completion_time=duration + grace_period)
    assert should_include(request_at_cutoff) is True
```

```python
# BAD: Tests obvious behavior
def test_zero_plus_zero_equals_zero():
    """Test that 0 + 0 = 0."""
    assert 0 + 0 == 0
```

## What NOT to Test

### Don't Test Library Behavior

```python
# BAD: Testing asyncio
@pytest.mark.asyncio
async def test_asyncio_sleep_works():
    """Test that asyncio.sleep waits."""
    start = time.time()
    await asyncio.sleep(1)
    elapsed = time.time() - start
    assert 0.9 < elapsed < 1.1
```

**Why**: asyncio is already tested. We trust standard library.

### Don't Test Type System

```python
# BAD: Testing type hints
def test_function_accepts_int():
    """Test that function accepts int."""
    result = my_function(42)  # If type hints wrong, mypy catches it
    assert result is not None
```

**Why**: Type checkers (mypy) handle this. Runtime type checking is not Python's way.

### Don't Test Simple Properties

```python
# BAD: Testing calculated property
def test_in_progress_property():
    """Test that in_progress = sent - completed."""
    stats.sent = 10
    stats.completed = 3
    assert stats.in_progress == 7
```

**Why**: This tests arithmetic, not behavior. If `sent - completed` is wrong, many tests will fail naturally.

### Don't Test Obvious Chains

```python
# BAD: Testing method delegation
def test_service_stop_calls_base_stop():
    """Test that Service.stop calls BaseService.stop."""
    service = Service()
    with patch.object(BaseService, 'stop') as mock:
        await service.stop()
    mock.assert_called_once()
```

**Why**: This tests inheritance works. Python guarantees this.

## When to Mock vs Integration Test

### Mock External Dependencies

```python
# GOOD: Mock HTTP to test client behavior
with patch('aiohttp.ClientSession.post') as mock_post:
    mock_post.return_value = mock_response(status=500)
    result = await client.request(url)
    assert result.error is not None
```

**Why**: Tests client's error handling without requiring real HTTP server.

### Integration Test Internal Components

```python
# GOOD: Test real metric computation
metric = TTFTMetric()
result = metric.parse_record(actual_parsed_record, record_metrics)
assert result == expected_ttft_value
```

**Why**: Tests real metric logic. Mocking would test the mock, not the metric.

### Mock Sparingly

```python
# BAD: Over-mocking
with patch.object(metric, '_compute_value', return_value=42):
    result = metric.parse_record(record)
    assert result == 42
```

**Why**: This tests the mock returns 42, not that the metric computes correctly.

## Coverage Philosophy

**Coverage is an indicator, not a goal.**

- 100% coverage with bad tests = false confidence
- 80% coverage with good tests = real confidence
- Focus on critical paths, not coverage percentage

### High-Value Coverage Areas

1. **Error handling paths**: Do we recover correctly?
2. **Boundary conditions**: Off-by-one errors?
3. **State transitions**: Lifecycle correct?
4. **Resource cleanup**: No leaks?
5. **Integration points**: Services communicate correctly?

### Low-Value Coverage Areas

1. **Simple property getters**: `return self._value`
2. **Pydantic models**: Validation is Pydantic's job
3. **Standard library wrappers**: Trust the library
4. **Trivial forwarding**: `super().method()`

## Real Examples from AIPerf

### GOOD Test Example

From `tests/critical/test_credit_return_invariant.py`:

```python
def test_process_credit_drop_has_finally_block(self):
    """Verify _process_credit_drop_internal uses try-finally pattern.

    This is a structural test of CRITICAL importance. The finally block
    guarantees credit return even on exceptions.

    WHY TEST THIS:
    - Protects against accidental refactoring
    - Documents the critical pattern
    - Fails fast if someone breaks the guarantee
    """
    source = inspect.getsource(Worker._process_credit_drop_internal)
    assert "finally:" in source
    assert "credit_return_push_client.push" in source
```

**Why Good**:
- Tests a critical correctness guarantee
- Would catch real refactoring bugs
- Documents why the pattern exists
- Clear failure message

### BAD Test Example (Anti-pattern)

```python
# DON'T DO THIS
def test_credit_drop_message_has_request_id():
    """Test that CreditDropMessage has request_id field."""
    message = CreditDropMessage(
        request_id="test",
        phase=CreditPhase.PROFILING,
        ...
    )
    assert message.request_id == "test"
```

**Why Bad**:
- Tests Pydantic model construction
- Would only fail if Pydantic is broken
- Doesn't test any AIPerf behavior
- Wastes time reading and maintaining

## Testing Checklist

Before adding a test, verify:

- [ ] Tests a behavioral outcome, not implementation
- [ ] Would catch a real bug if code regresses
- [ ] Cannot be replaced by type checking or linting
- [ ] Tests AIPerf code, not libraries
- [ ] Has clear documentation of what bug it prevents
- [ ] Failure message would be actionable

If you answer "no" to any of these, reconsider the test.

## Summary

**Good tests**:
- Prevent real bugs
- Test behavior
- Are maintainable
- Provide confidence

**Bad tests**:
- Achieve coverage numbers
- Test implementation
- Break on refactoring
- Provide false confidence

**Focus**: Write fewer, better tests that verify critical guarantees.

## See Also

- `/tests/critical/` - Critical invariant tests
- `/guidebook/chapter-40-testing-strategies.md` - Testing strategies guide
- `/CLAUDE.md` - Testing guidelines section

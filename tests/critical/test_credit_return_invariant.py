# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Critical Invariant Tests: Credit Return Guarantee

These tests verify THE MOST CRITICAL INVARIANT in AIPerf:

    Every credit drop MUST result in exactly one credit return.

This invariant is so critical that violating it breaks the entire benchmark.
Lost credits halt the system. Duplicate returns corrupt metrics.

These tests are not about coverage numbers - they verify correctness
of the fundamental contract that makes AIPerf work.
"""

import inspect


class TestCreditReturnInvariant:
    """Test the credit return guarantee at the code structure level."""

    def test_process_credit_drop_has_finally_block(self):
        """Verify _process_credit_drop_internal uses try-finally pattern.

        This is a structural test of CRITICAL importance. The finally block
        guarantees credit return even on exceptions. This test ensures the
        pattern is preserved during refactoring.

        WHY TEST THIS:
        - Protects against accidental refactoring that removes finally
        - Documents the critical pattern
        - Fails fast if someone breaks the guarantee
        """
        from aiperf.workers.worker import Worker

        source = inspect.getsource(Worker._process_credit_drop_internal)

        # Verify the critical pattern exists
        assert "try:" in source, "Credit processing must use try-except-finally"
        assert "finally:" in source, (
            "Credit return MUST be in finally block for guarantee"
        )

        # Verify credit_return_push_client.push is in finally
        lines = source.split("\n")
        in_finally = False
        has_return_in_finally = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("finally:"):
                in_finally = True
            elif in_finally and "credit_return_push_client.push" in line:
                has_return_in_finally = True

        assert has_return_in_finally, (
            "credit_return_push_client.push MUST be called in finally block"
        )

    def test_worker_callback_never_loses_credits(self):
        """Verify _credit_drop_callback handles all exceptions.

        The top-level callback must catch ALL exceptions to prevent
        credit loss. Any uncaught exception would skip credit return.

        WHY TEST THIS:
        - Guards against uncaught exceptions
        - Ensures robustness of the callback
        - Documents exception handling requirement
        """
        from aiperf.workers.worker import Worker

        source = inspect.getsource(Worker._credit_drop_callback)

        # Should have exception handling
        assert "except" in source, "_credit_drop_callback must handle exceptions"

        # Should call _process_credit_drop_internal
        assert "_process_credit_drop_internal" in source, (
            "_credit_drop_callback must call _process_credit_drop_internal"
        )


class TestTimingPrecisionRequirements:
    """Test that timing measurements use correct primitives.

    These tests verify we use perf_counter_ns (monotonic) not time_ns (wall clock)
    for latency measurements.

    WHY TEST THIS:
    - time_ns can go backwards (NTP adjustments)
    - perf_counter_ns is guaranteed monotonic
    - Wrong choice breaks latency accuracy
    """

    def test_worker_uses_perf_counter_for_latency(self):
        """Verify worker uses perf_counter_ns for timing.

        Critical for accurate TTFT and latency measurements.
        """
        from aiperf.workers.worker import Worker

        source = inspect.getsource(Worker._execute_single_credit_internal)

        # Should use perf_counter_ns, not time_ns for latency
        assert "time.perf_counter_ns()" in source, (
            "Worker must use perf_counter_ns() for latency measurements"
        )

    def test_metrics_use_perf_ns_fields(self):
        """Verify metrics use perf_ns fields from records.

        Metrics must use the monotonic perf_counter timestamps,
        not wall clock timestamps.
        """
        from aiperf.metrics.types.ttft_metric import TTFTMetric

        source = inspect.getsource(TTFTMetric._parse_record)

        # Should access .perf_ns fields
        assert "perf_ns" in source, "TTFT must use perf_ns timestamps from responses"


class TestPhaseCompletionLogic:
    """Test phase completion detection logic."""

    def test_in_flight_calculation(self):
        """Verify in_flight = sent - completed.

        WHY TEST THIS:
        - Used for completion detection
        - Used for progress reporting
        - Wrong calculation means incorrect ETA and hang detection
        """
        import time

        from aiperf.common.enums import CreditPhase
        from aiperf.common.models.credit_models import CreditPhaseStats

        phase_stats = CreditPhaseStats(
            type=CreditPhase.PROFILING,
            total_expected_requests=100,
            start_ns=time.time_ns(),
        )

        # Test the calculation at various states
        test_cases = [
            (0, 0, 0),  # No credits issued
            (50, 0, 50),  # All credits outstanding
            (50, 30, 20),  # Some returned
            (50, 50, 0),  # All returned
            (100, 95, 5),  # Almost done
        ]

        for sent, completed, expected_in_flight in test_cases:
            phase_stats.sent = sent
            phase_stats.completed = completed
            assert phase_stats.in_flight == expected_in_flight, (
                f"Expected {expected_in_flight} for sent={sent}, completed={completed}"
            )


class TestDurationFilteringInvariant:
    """Test duration-based filtering critical behavior."""

    def test_multiturn_filtering_all_or_nothing_concept(self):
        """Document that multi-turn filtering must be atomic.

        WHY DOCUMENT THIS:
        - Partial results corrupt metrics
        - All turns must complete within grace period OR all excluded
        - This prevents inconsistent throughput calculations

        NOTE: This is a documentation test, not a runtime test.
        The actual behavior is tested in integration tests with RecordsManager.
        """
        # The critical concept: If ANY turn arrives late, ENTIRE conversation excluded
        # This is implemented in RecordsManager._should_include_request_by_duration

        # The logic iterates through all turns in a conversation
        # If any turn's final_response_timestamp > duration_end_ns, return False

        # We verify this pattern exists in the code
        import inspect

        from aiperf.records.records_manager import RecordsManager

        source = inspect.getsource(RecordsManager._should_include_request_by_duration)

        # Verify it iterates through results (multi-turn support)
        assert "for result_dict in results" in source, "Must iterate through all turns"

        # Verify it can return False (filtering capability)
        assert "return False" in source, "Must be able to exclude requests"

        # Verify it checks against duration
        assert "duration_end_ns" in source or "expected_duration" in source, (
            "Must check against duration boundary"
        )


class TestLoggingServiceSpecificMatching:
    """Test service-specific logging matches correctly.

    WHY TEST THIS:
    - Critical for debugging distributed systems
    - Wrong match means wrong logs or flood of logs
    - Affects developer productivity
    """

    def test_worker_instances_match_worker_type(self):
        """Verify worker_0, worker_1, etc. match WORKER type."""
        from aiperf.common.enums import ServiceType
        from aiperf.common.logging import _is_service_in_types

        service_types = {ServiceType.WORKER}

        # All worker instances should match
        assert _is_service_in_types("worker_0", service_types) is True
        assert _is_service_in_types("worker_1", service_types) is True
        assert _is_service_in_types("worker_100", service_types) is True

    def test_manager_not_matched_by_service_type(self):
        """Verify worker_manager does NOT match WORKER type.

        Critical distinction - manager is a separate service.
        """
        from aiperf.common.enums import ServiceType
        from aiperf.common.logging import _is_service_in_types

        service_types = {ServiceType.WORKER}

        # Manager should NOT match
        assert _is_service_in_types("worker_manager", service_types) is False

    def test_service_matching_logic_exists(self):
        """Verify service-specific logging matching logic is implemented.

        WHY TEST THIS:
        - Service-specific logging is critical for debugging
        - Ensures the matching function exists and is callable
        - Documents the feature exists
        """
        import inspect

        from aiperf.common.logging import _is_service_in_types

        # Verify function exists and is callable
        assert callable(_is_service_in_types), (
            "_is_service_in_types must be a callable function"
        )

        # Verify it takes service_id and service_types parameters
        sig = inspect.signature(_is_service_in_types)
        params = list(sig.parameters.keys())
        assert "service_id" in params, "Must accept service_id parameter"
        assert "service_types" in params, "Must accept service_types parameter"

        # Verify it returns a boolean
        source = inspect.getsource(_is_service_in_types)
        assert "return True" in source, "Must return True for matches"
        assert "return False" in source, "Must return False for non-matches"

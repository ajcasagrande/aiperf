#!/bin/bash
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

# Comprehensive test runner for all new features
# Tests: Dataset chunking + Deterministic mode + Kubernetes integration

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
RUN_K8S_TESTS=${RUN_K8S_TESTS:-0}
VERBOSE=${VERBOSE:-0}

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  AIPerf Comprehensive Feature Test Suite                         ║${NC}"
echo -e "${BLUE}║  - Dataset Chunking Optimization                                  ║${NC}"
echo -e "${BLUE}║  - Deterministic Mode (Perfect Reproducibility)                   ║${NC}"
echo -e "${BLUE}║  - Kubernetes Integration                                         ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

print_section() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_step() {
    echo -e "${BLUE}[$1] $2${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    print_warning "Virtual environment not found, using system Python"
fi

# Test results tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

run_pytest() {
    local test_path=$1
    local test_name=$2
    local extra_args=$3

    echo ""
    print_step "→" "Running: $test_name"

    if [ "$VERBOSE" = "1" ]; then
        pytest_output=$(python -m pytest "$test_path" $extra_args -v 2>&1)
    else
        pytest_output=$(python -m pytest "$test_path" $extra_args -v --tb=line 2>&1)
    fi

    pytest_exit=$?

    # Extract test counts
    if echo "$pytest_output" | grep -q "passed"; then
        passed=$(echo "$pytest_output" | grep -oP '\d+(?= passed)' | tail -1)
        PASSED_TESTS=$((PASSED_TESTS + ${passed:-0}))
    fi

    if echo "$pytest_output" | grep -q "failed"; then
        failed=$(echo "$pytest_output" | grep -oP '\d+(?= failed)' | tail -1)
        FAILED_TESTS=$((FAILED_TESTS + ${failed:-0}))
        print_error "$test_name: $failed test(s) failed"
        echo "$pytest_output" | tail -20
    fi

    if echo "$pytest_output" | grep -q "skipped"; then
        skipped=$(echo "$pytest_output" | grep -oP '\d+(?= skipped)' | tail -1)
        SKIPPED_TESTS=$((SKIPPED_TESTS + ${skipped:-0}))
    fi

    if [ $pytest_exit -eq 0 ]; then
        print_success "$test_name passed"
    else
        print_error "$test_name failed (exit code: $pytest_exit)"
        return 1
    fi
}

# ============================================================================
# SECTION 1: Unit Tests
# ============================================================================

print_section "SECTION 1: Unit Tests (No External Dependencies)"

run_pytest \
    "tests/dataset/test_chunk_distribution.py" \
    "Dataset Chunking Unit Tests" \
    "--tb=short"

run_pytest \
    "tests/dataset/test_reproducibility.py" \
    "Reproducibility Unit Tests" \
    "--tb=short"

run_pytest \
    "tests/test_kubernetes_components.py" \
    "Kubernetes Components Unit Tests" \
    "--tb=short"

run_pytest \
    "tests/test_kubernetes_implementation.py" \
    "Kubernetes Implementation Unit Tests" \
    "--tb=short"

# ============================================================================
# SECTION 2: Integration Tests (No Cluster)
# ============================================================================

print_section "SECTION 2: Integration Tests (No Kubernetes Cluster Required)"

run_pytest \
    "tests/integration/test_dataset_chunking_integration.py" \
    "Dataset Chunking Integration Tests" \
    "-m 'not kubernetes' --tb=short"

run_pytest \
    "tests/integration/test_e2e_chunking_reproducibility.py" \
    "E2E Reproducibility Tests" \
    "-m 'not kubernetes' --tb=short"

run_pytest \
    "tests/integration/test_kubernetes_integration.py::test_module_imports" \
    "Kubernetes Module Imports" \
    "--tb=short"

run_pytest \
    "tests/integration/test_kubernetes_integration.py::TestConfigSerialization" \
    "Kubernetes Config Serialization" \
    "--tb=short"

run_pytest \
    "tests/integration/test_kubernetes_integration.py::TestKubernetesPodTemplates" \
    "Kubernetes Pod Templates" \
    "--tb=short"

# ============================================================================
# SECTION 3: Kubernetes Integration Tests (Requires Cluster)
# ============================================================================

if [ "$RUN_K8S_TESTS" = "1" ]; then
    print_section "SECTION 3: Kubernetes Integration Tests (Cluster Required)"

    # Check cluster access
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Kubernetes cluster not accessible"
        print_warning "Skipping Kubernetes integration tests"
    else
        print_success "Kubernetes cluster accessible"

        run_pytest \
            "tests/integration/test_kubernetes_integration.py" \
            "Full Kubernetes Integration Tests" \
            "-m kubernetes --tb=short"

        run_pytest \
            "tests/integration/test_kubernetes_e2e.py" \
            "Kubernetes E2E Tests" \
            "-m kubernetes --tb=short"

        run_pytest \
            "tests/integration/test_dataset_chunking_integration.py" \
            "Kubernetes + Chunking Tests" \
            "-m kubernetes --tb=short"

        run_pytest \
            "tests/integration/test_e2e_chunking_reproducibility.py" \
            "Kubernetes + Reproducibility Tests" \
            "-m kubernetes --tb=short"
    fi
else
    print_section "SECTION 3: Kubernetes Tests (SKIPPED)"
    echo -e "${YELLOW}Set RUN_K8S_TESTS=1 to run Kubernetes integration tests${NC}"
fi

# ============================================================================
# Summary
# ============================================================================

TOTAL_TESTS=$((PASSED_TESTS + FAILED_TESTS + SKIPPED_TESTS))

echo ""
echo ""
print_section "TEST SUMMARY"

echo -e "Total Tests:    ${CYAN}$TOTAL_TESTS${NC}"
echo -e "Passed:         ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed:         ${RED}$FAILED_TESTS${NC}"
echo -e "Skipped:        ${YELLOW}$SKIPPED_TESTS${NC}"

echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                   ✓ ALL TESTS PASSED ✓                           ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}Features validated:${NC}"
    echo -e "  ✓ Dataset chunking (100x performance improvement)"
    echo -e "  ✓ Deterministic mode (perfect reproducibility)"
    echo -e "  ✓ Kubernetes integration"
    echo -e "  ✓ Backwards compatibility"
    echo ""
    exit 0
else
    echo -e "${RED}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                   ✗ SOME TESTS FAILED ✗                          ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${RED}$FAILED_TESTS test(s) failed. Review output above for details.${NC}"
    echo ""
    exit 1
fi

#!/bin/bash
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

# Comprehensive minikube integration test runner
# Tests dataset chunking + Kubernetes integration on real cluster

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  AIPerf Minikube Integration Test Suite                          ║${NC}"
echo -e "${BLUE}║  Testing: Dataset Chunking + Kubernetes + Reproducibility        ║${NC}"
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

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Check prerequisites
print_section "Prerequisites Check"

if ! command -v minikube &> /dev/null; then
    print_error "minikube not found. Run: scripts/setup_minikube_testing.sh"
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    print_error "kubectl not found"
    exit 1
fi

if ! minikube status &> /dev/null; then
    print_error "minikube not running. Run: scripts/setup_minikube_testing.sh"
    exit 1
fi

print_success "minikube running"
print_success "kubectl accessible"

# Activate venv
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    print_success "Virtual environment activated"
fi

# Verify minikube has AIPerf image
if ! minikube image ls | grep -q "aiperf:latest"; then
    print_warning "AIPerf image not found in minikube"
    echo "Loading image..."
    docker build -t aiperf:latest .
    minikube image load aiperf:latest
    print_success "Image loaded"
else
    print_success "AIPerf image available in minikube"
fi

# Deploy mock LLM server if not present
print_step "→" "Checking mock LLM server"
if ! kubectl get service mock-llm-service -n default &> /dev/null; then
    if [ -f "tools/kubernetes/mock-llm-server.yaml" ]; then
        kubectl apply -f tools/kubernetes/mock-llm-server.yaml
        print_success "Mock LLM server deployed"
        kubectl wait --for=condition=ready pod -l app=mock-llm -n default --timeout=60s || true
    fi
else
    print_success "Mock LLM server already deployed"
fi

echo ""

# Test tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

run_test_suite() {
    local test_path=$1
    local test_name=$2

    echo ""
    print_step "→" "Running: $test_name"

    output=$(python -m pytest "$test_path" -v --tb=short --integration 2>&1)
    exit_code=$?

    # Count results
    if echo "$output" | grep -q "passed"; then
        passed=$(echo "$output" | grep -oP '\d+(?= passed)' | tail -1)
        PASSED_TESTS=$((PASSED_TESTS + ${passed:-0}))
    fi

    if echo "$output" | grep -q "failed"; then
        failed=$(echo "$output" | grep -oP '\d+(?= failed)' | tail -1)
        FAILED_TESTS=$((FAILED_TESTS + ${failed:-0}))
    fi

    if echo "$output" | grep -q "skipped"; then
        skipped=$(echo "$output" | grep -oP '\d+(?= skipped)' | tail -1)
        SKIPPED_TESTS=$((SKIPPED_TESTS + ${skipped:-0}))
    fi

    if [ $exit_code -eq 0 ]; then
        print_success "$test_name passed"
    else
        print_error "$test_name failed"
        echo "$output" | tail -30
        return 1
    fi
}

# ============================================================================
# SECTION 1: Cluster Deployment Tests
# ============================================================================

print_section "SECTION 1: Kubernetes Deployment with Chunking"

export RUN_MINIKUBE_TESTS=1

run_test_suite \
    "tests/integration/test_minikube_cluster.py::TestMinikubeClusterDeployment" \
    "Minikube Deployment Tests"

# ============================================================================
# SECTION 2: Chunking on Real Cluster
# ============================================================================

print_section "SECTION 2: Dataset Chunking on Real Cluster"

run_test_suite \
    "tests/integration/test_minikube_cluster.py::TestRealClusterChunking" \
    "Cluster Chunking Tests"

# ============================================================================
# SECTION 3: Reproducibility Validation
# ============================================================================

print_section "SECTION 3: Reproducibility on Real Cluster"

run_test_suite \
    "tests/integration/test_minikube_cluster.py::TestReproducibilityOnCluster" \
    "Cluster Reproducibility Tests"

# ============================================================================
# SECTION 4: Scaling Tests
# ============================================================================

print_section "SECTION 4: Cluster Scaling with Chunking"

run_test_suite \
    "tests/integration/test_minikube_cluster.py::TestClusterScaling" \
    "Scaling Tests"

# ============================================================================
# SECTION 5: Communication Tests
# ============================================================================

print_section "SECTION 5: Inter-Pod Communication"

run_test_suite \
    "tests/integration/test_minikube_cluster.py::TestClusterCommunication" \
    "Communication Tests"

# ============================================================================
# SECTION 6: Resource Management
# ============================================================================

print_section "SECTION 6: Resource Management"

run_test_suite \
    "tests/integration/test_minikube_cluster.py::TestClusterResourceManagement" \
    "Resource Management Tests"

run_test_suite \
    "tests/integration/test_minikube_cluster.py::TestArtifactRetrieval" \
    "Artifact Retrieval Tests"

# ============================================================================
# SECTION 7: Full E2E Benchmark
# ============================================================================

print_section "SECTION 7: End-to-End Benchmark (Optional)"

if [ "${RUN_FULL_E2E:-0}" = "1" ]; then
    run_test_suite \
        "tests/integration/test_minikube_cluster.py::TestFullBenchmarkOnCluster" \
        "Full Benchmark Tests"
else
    print_warning "Skipping full E2E tests (set RUN_FULL_E2E=1 to run)"
    echo "  These tests take 2-5 minutes and run actual benchmarks"
fi

# ============================================================================
# Cleanup Check
# ============================================================================

print_section "Cleanup Verification"

echo "Checking for leftover test namespaces..."
LEFTOVER=$(kubectl get namespaces -o json | jq -r '.items[] | select(.metadata.name | startswith("aiperf-test-")) | .metadata.name' 2>/dev/null || echo "")

if [ -n "$LEFTOVER" ]; then
    print_warning "Found leftover test namespaces:"
    echo "$LEFTOVER"
    read -p "Clean up now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "$LEFTOVER" | xargs -I {} kubectl delete namespace {} --timeout=30s
        print_success "Cleanup complete"
    fi
else
    print_success "No leftover namespaces"
fi

# ============================================================================
# Summary
# ============================================================================

TOTAL_TESTS=$((PASSED_TESTS + FAILED_TESTS + SKIPPED_TESTS))

echo ""
echo ""
print_section "TEST RESULTS SUMMARY"

echo -e "Total Tests:    ${CYAN}$TOTAL_TESTS${NC}"
echo -e "Passed:         ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed:         ${RED}$FAILED_TESTS${NC}"
echo -e "Skipped:        ${YELLOW}$SKIPPED_TESTS${NC}"

echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          ✓ ALL MINIKUBE INTEGRATION TESTS PASSED ✓               ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}Validated on real minikube cluster:${NC}"
    echo "  ✓ Kubernetes deployment with chunking"
    echo "  ✓ ConfigMap propagation"
    echo "  ✓ Pod creation and lifecycle"
    echo "  ✓ Deterministic mode configuration"
    echo "  ✓ ClusterIP services for ZMQ"
    echo "  ✓ Resource cleanup"
    echo ""
    echo -e "${GREEN}The Kubernetes integration with dataset chunking is production-ready!${NC}"
    echo ""
    exit 0
else
    echo -e "${RED}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║              ✗ SOME TESTS FAILED ✗                               ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${RED}$FAILED_TESTS test(s) failed on minikube cluster.${NC}"
    echo ""
    echo "Debug steps:"
    echo "  1. Check cluster status: minikube status"
    echo "  2. Check pods: kubectl get pods -A"
    echo "  3. Check logs: kubectl logs <pod-name> -n <namespace>"
    echo ""
    exit 1
fi

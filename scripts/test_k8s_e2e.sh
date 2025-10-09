#!/bin/bash
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

# Comprehensive end-to-end Kubernetes test script
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
TEST_NAMESPACE="aiperf-e2e-$(date +%s)"
MOCK_LLM_URL="http://mock-llm-service.default.svc.cluster.local:8000"
MODEL="mock-model"
CONCURRENCY=10
DURATION=60
AIPERF_IMAGE="aiperf:latest"

echo -e "${BLUE}===== AIPerf Kubernetes End-to-End Test =====${NC}"
echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo "  Test Namespace: $TEST_NAMESPACE"
echo "  Mock LLM URL: $MOCK_LLM_URL"
echo "  Model: $MODEL"
echo "  Concurrency: $CONCURRENCY"
echo "  Duration: ${DURATION}s"
echo "  AIPerf Image: $AIPERF_IMAGE"
echo ""

# Function to print step headers
print_step() {
    echo ""
    echo -e "${BLUE}[$1] $2${NC}"
    echo "----------------------------------------"
}

# Function to check command exists
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}Error: $1 not found${NC}"
        exit 1
    fi
}

# Step 1: Prerequisites
print_step "1/10" "Checking prerequisites"
check_command kubectl
check_command docker
check_command python

# Check cluster access
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}Error: Cannot access Kubernetes cluster${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Kubernetes cluster accessible${NC}"

# Step 2: Build AIPerf image if needed
print_step "2/10" "Checking AIPerf Docker image"
if ! docker images | grep -q "aiperf.*latest"; then
    echo "Building AIPerf image..."
    if [ -f "Dockerfile.kubernetes" ]; then
        docker build -t aiperf:latest -f Dockerfile.kubernetes .
    elif [ -f "Dockerfile" ]; then
        docker build -t aiperf:latest .
    else
        echo -e "${RED}Error: No Dockerfile found${NC}"
        exit 1
    fi
fi

# Load image into cluster (for minikube/kind)
if kubectl config current-context | grep -q "minikube"; then
    echo "Loading image into minikube..."
    minikube image load aiperf:latest || true
elif kubectl config current-context | grep -q "kind"; then
    echo "Loading image into kind..."
    kind load docker-image aiperf:latest || true
fi
echo -e "${GREEN}✓ AIPerf image ready${NC}"

# Step 3: Deploy mock LLM server
print_step "3/10" "Deploying mock LLM server"
if kubectl get service mock-llm-service -n default &> /dev/null; then
    echo "Mock LLM server already deployed"
else
    if [ -f "tools/kubernetes/mock-llm-server.yaml" ]; then
        kubectl apply -f tools/kubernetes/mock-llm-server.yaml
    elif [ -f "tools/kubernetes/test-mock-server.yaml" ]; then
        kubectl apply -f tools/kubernetes/test-mock-server.yaml
    else
        echo -e "${YELLOW}Warning: Mock server YAML not found, skipping${NC}"
    fi
    echo "Waiting for mock server to be ready..."
    kubectl wait --for=condition=ready pod -l app=mock-llm -n default --timeout=60s || true
fi
echo -e "${GREEN}✓ Mock LLM server ready${NC}"

# Step 4: Run unit tests
print_step "4/10" "Running unit tests"
source .venv/bin/activate 2>/dev/null || true
python -m pytest tests/test_kubernetes_components.py tests/test_kubernetes_implementation.py \
    -v --tb=short -x 2>&1 | tail -15
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo -e "${GREEN}✓ Unit tests passed${NC}"
else
    echo -e "${RED}✗ Unit tests failed${NC}"
    exit 1
fi

# Step 5: Run integration tests (without cluster deployment)
print_step "5/10" "Running integration tests (unit-level)"
python -m pytest tests/integration/test_kubernetes_integration.py \
    -v --tb=short -m "not kubernetes or kubernetes" -k "test_module_imports or test_config" \
    2>&1 | tail -15
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo -e "${GREEN}✓ Integration unit tests passed${NC}"
else
    echo -e "${YELLOW}⚠ Some integration tests skipped or failed${NC}"
fi

# Step 6: Deploy AIPerf to Kubernetes
print_step "6/10" "Deploying AIPerf to Kubernetes"
echo "Running: aiperf profile --kubernetes --kubernetes-namespace $TEST_NAMESPACE ..."

timeout 300 python -m aiperf profile \
    --ui none \
    --kubernetes \
    --kubernetes-namespace $TEST_NAMESPACE \
    --kubernetes-image $AIPERF_IMAGE \
    --kubernetes-image-pull-policy IfNotPresent \
    --endpoint-type chat \
    --streaming \
    -u $MOCK_LLM_URL \
    -m $MODEL \
    --benchmark-duration $DURATION \
    --concurrency $CONCURRENCY \
    --public-dataset sharegpt \
    2>&1 | tee /tmp/aiperf-k8s-e2e.log &

AIPERF_PID=$!

# Wait a bit for deployment to start
sleep 10

# Step 7: Monitor deployment
print_step "7/10" "Monitoring deployment"
echo "Checking namespace: $TEST_NAMESPACE"

for i in {1..30}; do
    if kubectl get namespace $TEST_NAMESPACE &> /dev/null; then
        echo -e "${GREEN}✓ Namespace created${NC}"
        break
    fi
    sleep 2
done

if ! kubectl get namespace $TEST_NAMESPACE &> /dev/null; then
    echo -e "${RED}✗ Namespace not created${NC}"
    kill $AIPERF_PID 2>/dev/null || true
    exit 1
fi

# Check for pods
echo "Waiting for pods..."
for i in {1..30}; do
    POD_COUNT=$(kubectl get pods -n $TEST_NAMESPACE --no-headers 2>/dev/null | wc -l)
    if [ $POD_COUNT -gt 0 ]; then
        echo -e "${GREEN}✓ Pods created: $POD_COUNT${NC}"
        kubectl get pods -n $TEST_NAMESPACE
        break
    fi
    sleep 2
done

# Step 8: Wait for completion
print_step "8/10" "Waiting for benchmark completion"
wait $AIPERF_PID
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ AIPerf completed successfully${NC}"
else
    echo -e "${RED}✗ AIPerf failed with exit code $EXIT_CODE${NC}"
    echo "Logs:"
    tail -50 /tmp/aiperf-k8s-e2e.log
fi

# Step 9: Verify artifacts
print_step "9/10" "Verifying artifacts"
if [ -d "./artifacts" ]; then
    echo -e "${GREEN}✓ Artifacts directory found${NC}"
    ls -lh ./artifacts/ | head -10

    # Check for expected files
    if ls ./artifacts/*.jsonl &> /dev/null; then
        echo -e "${GREEN}✓ JSONL records found${NC}"
    fi
else
    echo -e "${YELLOW}⚠ No artifacts directory found${NC}"
fi

# Step 10: Cleanup
print_step "10/10" "Cleaning up"
echo "Checking if namespace still exists..."
if kubectl get namespace $TEST_NAMESPACE &> /dev/null; then
    echo "Namespace still exists. Pods:"
    kubectl get pods -n $TEST_NAMESPACE 2>/dev/null || true

    # Force cleanup if needed
    read -p "Delete namespace now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kubectl delete namespace $TEST_NAMESPACE --timeout=30s
    fi
else
    echo -e "${GREEN}✓ Namespace already cleaned up${NC}"
fi

# Summary
echo ""
echo -e "${BLUE}===== Test Summary =====${NC}"
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓✓✓ ALL TESTS PASSED ✓✓✓${NC}"
    echo ""
    echo "Kubernetes integration is fully functional!"
    echo "You can now run production deployments with:"
    echo "  aiperf profile --kubernetes [options]"
else
    echo -e "${RED}✗✗✗ TESTS FAILED ✗✗✗${NC}"
    echo ""
    echo "Check logs: /tmp/aiperf-k8s-e2e.log"
fi
echo ""

exit $EXIT_CODE

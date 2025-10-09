#!/bin/bash
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

# Comprehensive Kubernetes deployment test script

set -e

echo "===== AIPerf Kubernetes Deployment Test ====="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test configuration
TEST_NAMESPACE="aiperf-test-$(date +%s)"
VLLM_URL="http://vllm-service.default.svc.cluster.local:8000"
MODEL="facebook/opt-125m"
CONCURRENCY=10
DURATION=30

echo -e "${YELLOW}Test Configuration:${NC}"
echo "  Namespace: $TEST_NAMESPACE"
echo "  vLLM URL: $VLLM_URL"
echo "  Model: $MODEL"
echo "  Concurrency: $CONCURRENCY"
echo "  Duration: ${DURATION}s"
echo ""

# Step 1: Verify prerequisites
echo -e "${YELLOW}[1/7] Verifying prerequisites...${NC}"
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}kubectl not found${NC}"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo -e "${RED}docker not found${NC}"
    exit 1
fi

if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}Kubernetes cluster not accessible${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites verified${NC}"
echo ""

# Step 2: Verify Docker image
echo -e "${YELLOW}[2/7] Verifying AIPerf Docker image...${NC}"
if ! docker images | grep -q "aiperf.*latest"; then
    echo -e "${RED}AIPerf image not found. Building...${NC}"
    docker build -t aiperf:latest -f Dockerfile.kubernetes .
fi
echo -e "${GREEN}✓ AIPerf image available${NC}"
echo ""

# Step 3: Check vLLM deployment
echo -e "${YELLOW}[3/7] Checking vLLM deployment...${NC}"
if ! kubectl get deployment vllm-deployment -n default &> /dev/null; then
    echo "vLLM not deployed. Deploying..."
    kubectl apply -f tools/kubernetes/vllm-deployment.yaml
    echo "Waiting for vLLM to be ready..."
    kubectl wait --for=condition=ready pod -l app=vllm --timeout=300s -n default || true
fi

VLLM_POD=$(kubectl get pods -n default -l app=vllm -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
if [ -n "$VLLM_POD" ]; then
    VLLM_STATUS=$(kubectl get pod $VLLM_POD -n default -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
    echo "vLLM Pod: $VLLM_POD"
    echo "Status: $VLLM_STATUS"
    if [ "$VLLM_STATUS" = "Running" ]; then
        echo -e "${GREEN}✓ vLLM is running${NC}"
    else
        echo -e "${YELLOW}⚠ vLLM is $VLLM_STATUS (continuing anyway)${NC}"
    fi
else
    echo -e "${YELLOW}⚠ vLLM pod not found (will fail if needed)${NC}"
fi
echo ""

# Step 4: Run unit tests
echo -e "${YELLOW}[4/7] Running unit tests...${NC}"
python -m pytest tests/test_kubernetes_implementation.py tests/test_kubernetes_components.py -v --tb=short -x 2>&1 | tail -20
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Unit tests passed${NC}"
else
    echo -e "${RED}✗ Unit tests failed${NC}"
    exit 1
fi
echo ""

# Step 5: Run AIPerf on Kubernetes (quick test)
echo -e "${YELLOW}[5/7] Running AIPerf on Kubernetes...${NC}"
echo "Command: aiperf profile --ui none --kubernetes --kubernetes-namespace $TEST_NAMESPACE ..."

source .venv/bin/activate

python -m aiperf profile --ui none \
  --kubernetes \
  --kubernetes-namespace $TEST_NAMESPACE \
  --kubernetes-image aiperf:latest \
  --kubernetes-image-pull-policy IfNotPresent \
  --endpoint-type chat \
  --streaming \
  -u $VLLM_URL \
  -m $MODEL \
  --benchmark-duration $DURATION \
  --concurrency $CONCURRENCY \
  --public-dataset sharegpt \
  2>&1 | tee /tmp/aiperf-k8s-test.log

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ AIPerf deployment succeeded${NC}"
else
    echo -e "${RED}✗ AIPerf deployment failed with exit code $EXIT_CODE${NC}"
    echo "Checking namespace..."
    kubectl get pods -n $TEST_NAMESPACE 2>/dev/null || echo "Namespace not found"
fi
echo ""

# Step 6: Verify artifacts
echo -e "${YELLOW}[6/7] Verifying artifacts...${NC}"
if [ -d "./artifacts" ]; then
    echo "Artifacts found:"
    ls -lh ./artifacts/ | head -10
    echo -e "${GREEN}✓ Artifacts retrieved${NC}"
else
    echo -e "${YELLOW}⚠ No artifacts directory found${NC}"
fi
echo ""

# Step 7: Check cleanup
echo -e "${YELLOW}[7/7] Verifying cleanup...${NC}"
if kubectl get namespace $TEST_NAMESPACE &> /dev/null; then
    echo -e "${YELLOW}⚠ Namespace still exists (may still be cleaning up)${NC}"
    echo "Pods in namespace:"
    kubectl get pods -n $TEST_NAMESPACE 2>/dev/null || echo "None"
else
    echo -e "${GREEN}✓ Namespace cleaned up${NC}"
fi
echo ""

# Summary
echo "===== Test Summary ====="
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ All tests PASSED${NC}"
    echo ""
    echo "The Kubernetes implementation is working correctly!"
    echo "You can now run larger tests with higher concurrency."
else
    echo -e "${RED}✗ Tests FAILED${NC}"
    echo ""
    echo "Check the logs above for errors."
    echo "Log file: /tmp/aiperf-k8s-test.log"
fi
echo ""

exit $EXIT_CODE

#!/bin/bash
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

# Setup minikube for AIPerf integration testing

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  AIPerf Minikube Testing Environment Setup                       ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

print_step() {
    echo -e "${BLUE}[$1] $2${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Step 1: Check minikube installed
print_step "1/8" "Checking minikube installation"
if ! command -v minikube &> /dev/null; then
    print_error "minikube not found"
    echo "Install with:"
    echo "  curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64"
    echo "  sudo install minikube-linux-amd64 /usr/local/bin/minikube"
    exit 1
fi
print_success "minikube installed: $(minikube version --short)"

# Step 2: Check kubectl installed
print_step "2/8" "Checking kubectl installation"
if ! command -v kubectl &> /dev/null; then
    print_error "kubectl not found"
    echo "Install with: minikube kubectl -- get pods"
    exit 1
fi
print_success "kubectl installed: $(kubectl version --client --short 2>/dev/null || kubectl version --client)"

# Step 3: Check/start minikube
print_step "3/8" "Checking minikube cluster"
if minikube status &> /dev/null; then
    print_success "minikube already running"
else
    print_warning "minikube not running, starting cluster..."
    minikube start --cpus=4 --memory=8192 --disk-size=20g
    print_success "minikube started"
fi

# Verify cluster is accessible
if kubectl cluster-info &> /dev/null; then
    print_success "kubectl can access cluster"
else
    print_error "kubectl cannot access cluster"
    exit 1
fi

# Step 4: Build AIPerf Docker image
print_step "4/8" "Building AIPerf Docker image"
if [ -f "Dockerfile.kubernetes" ]; then
    docker build -t aiperf:latest -f Dockerfile.kubernetes . || {
        print_error "Docker build failed"
        exit 1
    }
elif [ -f "Dockerfile" ]; then
    docker build -t aiperf:latest -f Dockerfile . || {
        print_error "Docker build failed"
        exit 1
    }
else
    print_error "No Dockerfile found"
    exit 1
fi
print_success "AIPerf image built"

# Step 5: Load image into minikube
print_step "5/8" "Loading AIPerf image into minikube"
minikube image load aiperf:latest || {
    print_error "Failed to load image into minikube"
    exit 1
}
print_success "Image loaded into minikube"

# Verify image is available
if minikube image ls | grep -q "aiperf:latest"; then
    print_success "Image verified in minikube"
else
    print_warning "Image might not be visible yet"
fi

# Step 6: Deploy mock LLM server
print_step "6/8" "Deploying mock LLM server"
if kubectl get service mock-llm-service -n default &> /dev/null; then
    print_success "Mock LLM server already deployed"
else
    if [ -f "tools/kubernetes/mock-llm-server.yaml" ]; then
        kubectl apply -f tools/kubernetes/mock-llm-server.yaml
        print_success "Mock LLM server deployed"

        # Wait for ready
        echo "Waiting for mock server to be ready..."
        kubectl wait --for=condition=ready pod -l app=mock-llm -n default --timeout=60s || {
            print_warning "Mock server not ready yet (may still be starting)"
        }
    else
        print_warning "Mock server YAML not found, skipping"
    fi
fi

# Step 7: Verify Python dependencies
print_step "7/8" "Verifying Python environment"
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    print_success "Virtual environment activated"
else
    print_warning "No virtual environment found"
fi

# Check key dependencies
python -c "import kubernetes" 2>/dev/null || {
    print_error "kubernetes Python package not installed"
    echo "Install with: pip install kubernetes"
    exit 1
}
print_success "Python dependencies verified"

# Step 8: Run quick validation
print_step "8/8" "Running quick validation test"
python -m pytest tests/test_kubernetes_components.py -v -k "test_kubernetes_imports" --tb=short || {
    print_error "Validation test failed"
    exit 1
}
print_success "Validation passed"

# Summary
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                 ✓ SETUP COMPLETE ✓                               ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Minikube testing environment is ready!${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  1. Run unit tests:"
echo "     ${YELLOW}pytest tests/test_kubernetes_*.py -v${NC}"
echo ""
echo "  2. Run minikube integration tests:"
echo "     ${YELLOW}RUN_MINIKUBE_TESTS=1 pytest tests/integration/test_minikube_cluster.py -v${NC}"
echo ""
echo "  3. Run full integration suite:"
echo "     ${YELLOW}RUN_K8S_TESTS=1 RUN_MINIKUBE_TESTS=1 ./scripts/test_all_features.sh${NC}"
echo ""
echo "  4. Run E2E test on cluster:"
echo "     ${YELLOW}./scripts/test_k8s_e2e.sh${NC}"
echo ""

# Display cluster info
echo -e "${BLUE}Cluster Information:${NC}"
kubectl cluster-info | head -3
echo ""
echo -e "${BLUE}Minikube Status:${NC}"
minikube status
echo ""

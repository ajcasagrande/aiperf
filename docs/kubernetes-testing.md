<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Kubernetes Testing Guide

This document describes how to test the Kubernetes integration for AIPerf.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Test Levels](#test-levels)
- [Running Tests](#running-tests)
- [Test Environment Setup](#test-environment-setup)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Tools

- **kubectl**: Kubernetes CLI tool
- **docker**: Container runtime
- **python 3.10+**: AIPerf runtime
- **Kubernetes cluster**: One of:
  - minikube (recommended for local testing)
  - kind (Kubernetes in Docker)
  - Real Kubernetes cluster (GKE, EKS, AKS, etc.)

### Cluster Requirements

- **Minimum resources**:
  - 4 CPU cores
  - 8GB RAM
  - 20GB disk space
- **Permissions**: Ability to create namespaces, pods, services, ConfigMaps, RBAC resources

### Setup minikube (Recommended)

```bash
# Install minikube
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

# Start cluster
minikube start --cpus=4 --memory=8192

# Verify
kubectl cluster-info
```

## Quick Start

### 1. Install AIPerf

```bash
cd /path/to/aiperf
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Run Unit Tests

```bash
# Test Kubernetes components (no cluster required)
pytest tests/test_kubernetes_components.py -v
pytest tests/test_kubernetes_implementation.py -v
```

### 3. Deploy Mock LLM Server

```bash
# Deploy to default namespace
kubectl apply -f tools/kubernetes/mock-llm-server.yaml

# Wait for ready
kubectl wait --for=condition=ready pod -l app=mock-llm -n default --timeout=60s
```

### 4. Run End-to-End Test

```bash
# Run comprehensive E2E test
./scripts/test_k8s_e2e.sh
```

## Test Levels

### Level 1: Unit Tests (No Cluster Required)

Tests component functionality without Kubernetes cluster access.

**Files**:
- `tests/test_kubernetes_components.py` - Component unit tests
- `tests/test_kubernetes_implementation.py` - Implementation tests

**Run**:
```bash
pytest tests/test_kubernetes_components.py tests/test_kubernetes_implementation.py -v
```

**Coverage**:
- Pod template generation
- RBAC resource creation
- Configuration serialization/deserialization
- Service type handling

### Level 2: Integration Tests (Requires Cluster)

Tests that deploy actual resources to a Kubernetes cluster.

**Files**:
- `tests/integration/test_kubernetes_integration.py` - Full integration tests
- `tests/integration/test_kubernetes_e2e.py` - End-to-end tests

**Run**:
```bash
# Set environment variable to enable cluster tests
export RUN_K8S_TESTS=1

# Run all integration tests
pytest tests/integration/test_kubernetes_integration.py -v

# Run specific test class
pytest tests/integration/test_kubernetes_integration.py::TestKubernetesResourceManager -v
```

**Coverage**:
- Namespace creation/deletion
- Pod deployment and lifecycle
- ConfigMap creation/retrieval
- Service creation
- Resource cleanup
- Full benchmark deployment

### Level 3: End-to-End Tests (Full Deployment)

Complete deployment workflow with real benchmark execution.

**Files**:
- `scripts/test_k8s_e2e.sh` - Automated E2E test script
- `run_k8s_e2e_test.py` - Python E2E test

**Run**:
```bash
# Using bash script (recommended)
./scripts/test_k8s_e2e.sh

# Using Python script
python run_k8s_e2e_test.py
```

**What it tests**:
1. Prerequisites check
2. Docker image build/load
3. Mock LLM server deployment
4. Unit test execution
5. AIPerf Kubernetes deployment
6. Benchmark execution
7. Artifact retrieval
8. Resource cleanup

## Test Environment Setup

### Option 1: minikube

```bash
# Start minikube
minikube start --cpus=4 --memory=8192 --disk-size=20g

# Enable metrics (optional)
minikube addons enable metrics-server

# Load AIPerf image
docker build -t aiperf:latest .
minikube image load aiperf:latest
```

### Option 2: kind (Kubernetes in Docker)

```bash
# Create cluster
kind create cluster --name aiperf-test

# Load image
docker build -t aiperf:latest .
kind load docker-image aiperf:latest --name aiperf-test
```

### Option 3: Real Cluster

```bash
# Configure kubectl context
kubectl config use-context <your-cluster-context>

# Build and push image
docker build -t your-registry/aiperf:latest .
docker push your-registry/aiperf:latest

# Update image in tests
export AIPERF_K8S_IMAGE=your-registry/aiperf:latest
```

## Running Tests

### Run All Unit Tests

```bash
pytest tests/test_kubernetes_*.py -v
```

### Run Integration Tests (with cluster)

```bash
export RUN_K8S_TESTS=1
pytest tests/integration/test_kubernetes_integration.py -v
```

### Run Specific Test Class

```bash
export RUN_K8S_TESTS=1
pytest tests/integration/test_kubernetes_integration.py::TestKubernetesResourceManager -v
```

### Run End-to-End Test

```bash
# Full automated test
./scripts/test_k8s_e2e.sh

# Or manually with aiperf CLI
aiperf profile \
  --kubernetes \
  --kubernetes-namespace aiperf-test \
  --kubernetes-image aiperf:latest \
  --kubernetes-image-pull-policy IfNotPresent \
  --endpoint-type chat \
  --streaming \
  -u http://mock-llm-service.default.svc.cluster.local:8000 \
  -m mock-model \
  --benchmark-duration 60 \
  --concurrency 10 \
  --public-dataset sharegpt
```

## Test Artifacts

After running tests, artifacts are stored in:
- `./artifacts/` - Benchmark results (JSONL, JSON)
- `/tmp/aiperf-k8s-*.log` - Test execution logs

## Cleaning Up

### Manual Cleanup

```bash
# List AIPerf namespaces
kubectl get namespaces | grep aiperf

# Delete specific namespace
kubectl delete namespace <namespace-name>

# Force delete stuck namespace
kubectl delete namespace <namespace-name> --grace-period=0 --force
```

### Automated Cleanup

```bash
# Clean all aiperf test namespaces
kubectl get namespaces -o json | \
  jq -r '.items[] | select(.metadata.name | startswith("aiperf-")) | .metadata.name' | \
  xargs -I {} kubectl delete namespace {}
```

## Troubleshooting

### Issue: Pods not starting

**Symptom**: Pods stuck in `Pending` or `ImagePullBackOff`

**Solutions**:
```bash
# Check pod status
kubectl get pods -n <namespace>
kubectl describe pod <pod-name> -n <namespace>

# For minikube: Verify image is loaded
minikube image ls | grep aiperf

# Load image if missing
minikube image load aiperf:latest

# For kind: Load image
kind load docker-image aiperf:latest
```

### Issue: Permission denied errors

**Symptom**: `Error creating pod: forbidden`

**Solutions**:
```bash
# Check RBAC resources
kubectl get clusterrole | grep aiperf
kubectl get clusterrolebinding | grep aiperf

# Verify service account
kubectl get serviceaccount -n <namespace>

# Check current user permissions
kubectl auth can-i create pods
kubectl auth can-i create namespaces
```

### Issue: ConfigMap not found

**Symptom**: `Error reading ConfigMap: not found`

**Solutions**:
```bash
# List ConfigMaps
kubectl get configmaps -n <namespace>

# Describe ConfigMap
kubectl describe configmap aiperf-config -n <namespace>

# Verify config data
kubectl get configmap aiperf-config -n <namespace> -o yaml
```

### Issue: Tests timing out

**Symptom**: Tests hang or timeout

**Solutions**:
```bash
# Increase timeout in tests
export AIPERF_TEST_TIMEOUT=600

# Check pod logs
kubectl logs <pod-name> -n <namespace>

# Check system controller logs
kubectl logs -l service-type=system_controller -n <namespace>

# Check cluster resources
kubectl top nodes
kubectl top pods -n <namespace>
```

### Issue: Namespace stuck in Terminating

**Symptom**: `kubectl delete namespace` hangs

**Solutions**:
```bash
# Check what's blocking
kubectl get namespace <namespace> -o yaml

# Force delete (use with caution)
kubectl patch namespace <namespace> -p '{"metadata":{"finalizers":[]}}' --type=merge
kubectl delete namespace <namespace> --grace-period=0 --force
```

## Test Development

### Adding New Tests

1. **Unit tests**: Add to `tests/test_kubernetes_components.py`
2. **Integration tests**: Add to `tests/integration/test_kubernetes_integration.py`
3. **Mark appropriately**:

```python
import pytest

@pytest.mark.integration
@pytest.mark.kubernetes
class TestMyFeature:
    @requires_k8s_cluster()  # Skips if RUN_K8S_TESTS not set
    @pytest.mark.asyncio
    async def test_feature(self):
        # Your test here
        pass
```

### Test Fixtures

Common fixtures are available in `tests/integration/test_kubernetes_integration.py`:
- `test_namespace`: Unique test namespace
- `user_config`: Basic UserConfig
- `service_config`: ServiceConfig with K8s enabled
- `resource_manager`: KubernetesResourceManager with auto-cleanup

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Kubernetes Tests

on: [push, pull_request]

jobs:
  k8s-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run unit tests
        run: |
          pytest tests/test_kubernetes_*.py -v

      - name: Set up minikube
        run: |
          curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
          sudo install minikube-linux-amd64 /usr/local/bin/minikube
          minikube start --cpus=2 --memory=4096

      - name: Build and load image
        run: |
          docker build -t aiperf:latest .
          minikube image load aiperf:latest

      - name: Run integration tests
        env:
          RUN_K8S_TESTS: 1
        run: |
          pytest tests/integration/test_kubernetes_integration.py -v
```

## Additional Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)
- [minikube Documentation](https://minikube.sigs.k8s.io/docs/)
- [AIPerf Documentation](../README.md)

## Support

For issues or questions:
1. Check logs: `kubectl logs <pod-name> -n <namespace>`
2. Review cluster events: `kubectl get events -n <namespace>`
3. File an issue: [GitHub Issues](https://github.com/NVIDIA/aiperf/issues)

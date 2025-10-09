<!--
SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->

# AIPerf Kubernetes Deployment Guide

This guide explains how to deploy and run AIPerf in Kubernetes mode for distributed, high-concurrency benchmarking.

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration Options](#configuration-options)
- [Architecture](#architecture)
- [Deployment Modes](#deployment-modes)
- [Troubleshooting](#troubleshooting)
- [Advanced Usage](#advanced-usage)

---

## Overview

AIPerf Kubernetes mode enables distributed load generation across multiple pods, allowing you to:
- **Scale beyond single-node limits** (65K+ concurrent connections)
- **Generate 1M+ concurrent connections** with sufficient worker pods
- **Distribute load** across multiple nodes in a cluster
- **Leverage Kubernetes** for orchestration and resource management

### When to Use Kubernetes Mode

Use Kubernetes mode when you need:
- More than ~50K concurrent connections
- Distributed load generation across multiple nodes
- Testing production-scale scenarios
- Kubernetes-native deployment patterns

For most use cases under 50K concurrency, **single-node mode** (default) is simpler and sufficient.

---

## Prerequisites

### 1. Kubernetes Cluster

You need access to a Kubernetes cluster. Options include:

**Local Development:**
- **Minikube** (easiest for local testing)
- **Kind** (Kubernetes in Docker)
- **Docker Desktop** (built-in Kubernetes)

**Cloud Providers:**
- Google Kubernetes Engine (GKE)
- Amazon Elastic Kubernetes Service (EKS)
- Azure Kubernetes Service (AKS)

### 2. kubectl

Install and configure kubectl:
```bash
# Check kubectl is installed
kubectl version --client

# Verify cluster access
kubectl cluster-info
kubectl get nodes
```

### 3. Container Image

Build the AIPerf container image:
```bash
# Using make (recommended)
make k8s-build

# Or manually
docker build -t aiperf:latest .
```

For **Minikube**, load the image into Minikube's Docker:
```bash
make k8s-build-minikube
```

For **remote registries**, tag and push:
```bash
docker tag aiperf:latest your-registry/aiperf:latest
docker push your-registry/aiperf:latest
```

### 4. AIPerf Installation

Install AIPerf with Kubernetes support:
```bash
pip install -e ".[dev]"
```

---

## Quick Start

### 1. Start Local Cluster

```bash
# Using make
make k8s-cluster-start

# Or manually with minikube
minikube start --cpus=4 --memory=8192
```

### 2. Build Image

```bash
make k8s-build-minikube
```

### 3. Run Benchmark

```bash
aiperf profile \
  --kubernetes \
  --model your-model \
  --url http://your-llm-service:8000 \
  --endpoint-type chat \
  --streaming \
  --concurrency 100 \
  --request-count 500
```

### 4. Cleanup

```bash
# Cluster automatically cleans up namespace after completion
# To manually cleanup:
make k8s-cleanup

# Stop cluster when done
make k8s-cluster-stop
```

---

## Configuration Options

### Basic Kubernetes Flags

```bash
aiperf profile \
  --kubernetes \                          # Enable Kubernetes mode
  --kubernetes-namespace my-test \        # Custom namespace (optional)
  --kubeconfig ~/.kube/config \           # Custom kubeconfig (optional)
  --kubernetes-image aiperf:latest \      # Container image
  --model your-model \
  --url http://service:8000 \
  --endpoint-type chat \
  --concurrency 100
```

### Kubernetes-Specific Options

| Flag | Description | Default |
|------|-------------|---------|
| `--kubernetes` | Enable Kubernetes deployment mode | `false` |
| `--kubernetes-namespace` | Namespace to use (auto-generated if not specified) | `aiperf-{timestamp}-{id}` |
| `--kubeconfig` | Path to kubeconfig file | `~/.kube/config` |
| `--kubernetes-image` | Container image for pods | `aiperf:latest` |
| `--kubernetes-image-pull-policy` | Image pull policy | `IfNotPresent` |
| `--kubernetes-service-account` | ServiceAccount name | `aiperf-service-account` |
| `--kubernetes-auto-cleanup` | Auto-cleanup namespace after completion | `true` |

### Namespace Behavior

**Auto-generated namespace** (default):
```bash
aiperf profile --kubernetes ...
# Creates: aiperf-20251001-145030-abc123de
# Automatically cleaned up after completion
```

**Custom namespace** (persists):
```bash
aiperf profile --kubernetes --kubernetes-namespace my-test ...
# Uses: my-test
# NOT automatically cleaned up
```

---

## Architecture

### Pod Architecture

AIPerf deploys each service as a separate pod:

```
┌─────────────────────────────────────────┐
│  Namespace: aiperf-{timestamp}          │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ System Controller Pod           │   │
│  │ - Orchestrates benchmark        │   │
│  │ - Hosts ZMQ proxies             │   │
│  │ - Exposes ports via Service     │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ Dataset Manager Pod             │   │
│  │ - Manages benchmark data        │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ Timing Manager Pod              │   │
│  │ - Controls request timing       │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ Records Manager Pod             │   │
│  │ - Collects metrics              │   │
│  │ - Stores results                │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ Worker Manager Pod              │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ Worker Pods (N replicas)        │   │
│  │ - Execute inference requests    │   │
│  │ - Scale based on concurrency    │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ Record Processor Pods (M)       │   │
│  │ - Process responses             │   │
│  │ - Calculate metrics             │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

### Communication

All pods communicate via ZMQ over TCP through the System Controller Kubernetes Service:
- **Service DNS**: `aiperf-system-controller.{namespace}.svc.cluster.local`
- **Ports**: 5557, 5562, 5563, 5661-5666

### Scaling

Worker pods scale automatically based on:
- **Concurrency**: `--concurrency 100` creates ~1 worker per 500 connections
- **Workers Max**: `--workers-max` caps maximum workers
- **Record Processors**: `--record-processor-service-count` or auto-calculated

---

## Deployment Modes

### Mode 1: Auto-Generated Namespace (Recommended)

Perfect for quick tests and CI/CD:

```bash
aiperf profile \
  --kubernetes \
  --model test-model \
  --url http://service:8000 \
  --endpoint-type chat \
  --concurrency 1000 \
  --request-count 5000
```

**Behavior:**
- Creates unique namespace: `aiperf-20251001-145030-abc123de`
- Deploys all pods
- Runs benchmark
- Retrieves artifacts to local `./artifacts/`
- Automatically deletes namespace and all resources

### Mode 2: Custom Namespace (Persistent)

Good for debugging and iterative testing:

```bash
aiperf profile \
  --kubernetes \
  --kubernetes-namespace my-aiperf-test \
  --model test-model \
  --url http://service:8000 \
  --endpoint-type chat \
  --concurrency 1000 \
  --request-count 5000
```

**Behavior:**
- Uses existing or creates `my-aiperf-test` namespace
- Deploys all pods
- Runs benchmark
- Retrieves artifacts
- **Namespace persists** (manual cleanup required)

**Manual cleanup:**
```bash
kubectl delete namespace my-aiperf-test
```

### Mode 3: High Concurrency (100K+)

For production-scale load testing:

```bash
aiperf profile \
  --kubernetes \
  --model production-model \
  --url http://production-service:8000 \
  --endpoint-type chat \
  --streaming \
  --concurrency 100000 \
  --benchmark-duration 300 \
  --workers-max 200 \
  --record-processor-service-count 50
```

**This creates:**
- 200 worker pods (500 connections each)
- 50 record processor pods
- Runs for 5 minutes (300 seconds)

---

## Troubleshooting

### Check Pod Status

```bash
# List all pods
kubectl get pods -n aiperf-{namespace}

# Describe specific pod
kubectl describe pod {pod-name} -n aiperf-{namespace}

# Check pod logs
kubectl logs {pod-name} -n aiperf-{namespace}

# Follow logs in real-time
kubectl logs -f {pod-name} -n aiperf-{namespace}
```

### Common Issues

#### Issue: Pods stuck in "Pending"

**Symptoms:**
```bash
kubectl get pods -n aiperf-{namespace}
# Shows: STATUS=Pending
```

**Causes & Solutions:**
1. **Insufficient cluster resources**
   ```bash
   kubectl describe nodes
   # Check available CPU/memory
   # Solution: Reduce --concurrency or --workers-max
   ```

2. **Image pull errors**
   ```bash
   kubectl describe pod {pod-name} -n aiperf-{namespace}
   # Look for: ImagePullBackOff or ErrImagePull
   # Solution: Ensure image exists and is accessible
   ```

#### Issue: Pods in "CrashLoopBackOff"

**Symptoms:**
```bash
kubectl get pods -n aiperf-{namespace}
# Shows: STATUS=CrashLoopBackOff
```

**Solutions:**
```bash
# Check logs for errors
kubectl logs {pod-name} -n aiperf-{namespace}

# Common causes:
# 1. Configuration errors
# 2. Missing dependencies
# 3. Incorrect environment variables

# Debug by running pod interactively
kubectl run -it --rm debug \
  --image=aiperf:latest \
  --restart=Never \
  -- /bin/bash
```

#### Issue: Services fail to register

**Symptoms:**
```
ERROR: Services failed to register within timeout
```

**Solutions:**
1. **Check ZMQ communication**
   ```bash
   # Verify System Controller service exists
   kubectl get svc -n aiperf-{namespace}
   # Should show: aiperf-system-controller

   # Check service endpoints
   kubectl describe svc aiperf-system-controller -n aiperf-{namespace}
   ```

2. **Check pod network connectivity**
   ```bash
   # Test from a pod
   kubectl exec -it {worker-pod} -n aiperf-{namespace} -- \
     nc -zv aiperf-system-controller 5562
   ```

3. **Check pod logs**
   ```bash
   kubectl logs {pod-name} -n aiperf-{namespace} | grep -i error
   ```

#### Issue: Artifact retrieval fails

**Symptoms:**
```
WARNING: Failed to retrieve artifacts
```

**Solutions:**
```bash
# Manually retrieve artifacts
kubectl cp aiperf-{namespace}/{records-manager-pod}:/path/to/artifacts ./artifacts

# Find Records Manager pod
kubectl get pods -n aiperf-{namespace} -l service-type=records_manager
```

### Debug Commands

```bash
# Get all resources in namespace
kubectl get all -n aiperf-{namespace}

# Get events (helpful for debugging)
kubectl get events -n aiperf-{namespace} --sort-by='.lastTimestamp'

# Check RBAC permissions
kubectl auth can-i --list -n aiperf-{namespace} \
  --as=system:serviceaccount:aiperf-{namespace}:aiperf-service-account

# Port-forward to debug ZMQ
kubectl port-forward -n aiperf-{namespace} \
  svc/aiperf-system-controller 5562:5562
```

---

## Advanced Usage

### Custom Resource Limits

Create a custom pod spec override (future feature):

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: aiperf-worker
spec:
  containers:
  - name: aiperf-service
    resources:
      requests:
        memory: "2Gi"
        cpu: "2"
      limits:
        memory: "4Gi"
        cpu: "4"
```

### Using Custom kubeconfig

```bash
# Use specific cluster context
export KUBECONFIG=~/.kube/prod-config

aiperf profile \
  --kubernetes \
  --kubeconfig ~/.kube/prod-config \
  ...
```

### Testing with Mock Server

```bash
# Start mock server in Kubernetes
kubectl apply -f integration-tests/k8s-mock-server.yaml

# Run benchmark against mock server
aiperf profile \
  --kubernetes \
  --model test-model \
  --url http://mock-server.default.svc.cluster.local:8000 \
  --endpoint-type chat \
  --concurrency 100 \
  --request-count 500
```

### Multi-Cluster Deployment

For cross-cluster testing:

```bash
# Deploy on cluster 1
export KUBECONFIG=~/.kube/cluster1-config
aiperf profile --kubernetes --kubernetes-namespace aiperf-cluster1 ...

# Deploy on cluster 2
export KUBECONFIG=~/.kube/cluster2-config
aiperf profile --kubernetes --kubernetes-namespace aiperf-cluster2 ...
```

---

## Best Practices

### 1. Resource Planning

Calculate pod requirements:
```
Workers needed = Target Concurrency / 500
Record Processors = Workers / 4
Total Pods = Workers + Record Processors + 5 (core services)
```

Example for 100K concurrency:
```
Workers: 200 (100,000 / 500)
Record Processors: 50 (200 / 4)
Total Pods: 255
```

### 2. Namespace Management

- Use **auto-generated namespaces** for CI/CD and quick tests
- Use **custom namespaces** for debugging and development
- Always verify cleanup with: `kubectl get namespaces`

### 3. Image Management

- Use **specific tags** in production: `aiperf:v1.0.0`
- Use **latest** for development: `aiperf:latest`
- Use **IfNotPresent** policy for local images
- Use **Always** policy for registry images in CI/CD

### 4. Monitoring

```bash
# Watch pod status
watch kubectl get pods -n aiperf-{namespace}

# Monitor resource usage
kubectl top pods -n aiperf-{namespace}
kubectl top nodes

# Check for errors
kubectl get events -n aiperf-{namespace} | grep Warning
```

---

## Make Commands

The Makefile provides convenient shortcuts:

```bash
# Cluster management
make k8s-cluster-start      # Start minikube cluster
make k8s-cluster-stop       # Stop minikube cluster
make k8s-cluster-status     # Check cluster status

# Building
make k8s-build              # Build AIPerf image
make k8s-build-minikube     # Build and load into minikube
make k8s-push              # Push image to registry

# Testing
make k8s-test              # Run basic Kubernetes test
make k8s-test-high         # Run high concurrency test

# Cleanup
make k8s-cleanup           # Delete all AIPerf namespaces
make k8s-logs              # Get logs from all pods

# All-in-one
make k8s-demo              # Complete demo: start cluster, build, test
```

---

## Performance Tips

### 1. Optimize Worker Distribution

```bash
# More workers, lower concurrency per worker (better distribution)
--workers-max 400 --concurrency 100000  # 250 connections per worker

# Fewer workers, higher concurrency per worker (more efficient)
--workers-max 100 --concurrency 100000  # 1000 connections per worker
```

### 2. Adjust Record Processors

```bash
# High request rate? Increase record processors
--record-processor-service-count 100

# Low request rate? Reduce to save resources
--record-processor-service-count 10
```

### 3. Use Appropriate Duration

```bash
# Time-based (better for steady-state testing)
--benchmark-duration 600  # 10 minutes

# Request-count based (better for fixed workload)
--request-count 10000
```

---

## Next Steps

- Review [Architecture Documentation](architecture.md)
- Explore [Advanced Features](tutorials/)
- Check [Metrics Reference](metrics_reference.md)
- Read [Developer Guide](developer-guide.md) for internals

---

## Support

If you encounter issues:
1. Check [Troubleshooting](#troubleshooting) section
2. Review pod logs: `kubectl logs {pod} -n {namespace}`
3. Check events: `kubectl get events -n {namespace}`
4. Open an issue on GitHub with logs and configuration

Happy benchmarking! 🚀

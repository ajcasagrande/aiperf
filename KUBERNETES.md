<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Kubernetes Integration

Run AIPerf benchmarks at scale on Kubernetes clusters! 🚀

## Overview

The Kubernetes integration allows you to deploy and run AIPerf benchmarks on Kubernetes clusters, enabling:

- **Horizontal Scaling**: Run thousands of concurrent workers across multiple nodes
- **Resource Management**: Precise CPU/memory allocation for each component
- **Cloud-Native**: Deploy on any Kubernetes cluster (GKE, EKS, AKS, on-prem)
- **Isolation**: Each benchmark runs in its own namespace
- **Automatic Cleanup**: Resources are cleaned up after completion

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Local Machine (CLI)                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ aiperf profile --kubernetes ...                       │   │
│  │   ↓                                                    │   │
│  │ KubernetesOrchestrator                                │   │
│  │   • Creates namespace                                 │   │
│  │   • Deploys ConfigMap (user/service config)           │   │
│  │   • Creates RBAC resources                            │   │
│  │   • Deploys pods and services                         │   │
│  │   • Monitors completion                               │   │
│  │   • Retrieves artifacts                               │   │
│  │   • Cleans up resources                               │   │
│  └──────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │ kubectl API
┌───────────────────────────┼─────────────────────────────────┐
│                Kubernetes Cluster                            │
│  ┌────────────────────────────────────────────────────┐     │
│  │ Namespace: aiperf-YYYYMMDD-HHMMSS                  │     │
│  │                                                     │     │
│  │  ┌──────────────────────────────────────────────┐  │     │
│  │  │ System Controller Pod                         │  │     │
│  │  │  • Manages worker pools                       │  │     │
│  │  │  • Coordinates services                       │  │     │
│  │  │  • Handles ZMQ message routing                │  │     │
│  │  └──────────────────────────────────────────────┘  │     │
│  │                    ↓ ZMQ (ClusterIP Services)       │     │
│  │  ┌────────────┬────────────┬────────────────────┐  │     │
│  │  │ Worker     │ Worker     │ RecordProcessor    │  │     │
│  │  │ Pods       │ Pods       │ Pods               │  │     │
│  │  │  • Send    │  • Send    │  • Process         │  │     │
│  │  │  requests  │  requests  │    records         │  │     │
│  │  │  • Collect │  • Collect │  • Aggregate       │  │     │
│  │  │    metrics │    metrics │    metrics         │  │     │
│  │  └────────────┴────────────┴────────────────────┘  │     │
│  │                                                     │     │
│  │  Artifacts: Collected from pods → Local filesystem │     │
│  └────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Prerequisites

- Kubernetes cluster (minikube, kind, or cloud provider)
- kubectl configured
- Docker installed
- AIPerf installed: `pip install -e ".[dev]"`

### 2. Start a Cluster (using minikube)

```bash
minikube start --cpus=4 --memory=8192
```

### 3. Build and Load AIPerf Image

```bash
# Build image
docker build -t aiperf:latest .

# Load into minikube
minikube image load aiperf:latest
```

### 4. Deploy Mock LLM Server (for testing)

```bash
kubectl apply -f tools/kubernetes/mock-llm-server.yaml
kubectl wait --for=condition=ready pod -l app=mock-llm -n default --timeout=60s
```

### 5. Run a Benchmark

```bash
aiperf profile \
  --kubernetes \
  --kubernetes-image aiperf:latest \
  --kubernetes-image-pull-policy IfNotPresent \
  --endpoint-type chat \
  --streaming \
  -u http://mock-llm-service.default.svc.cluster.local:8000 \
  -m mock-model \
  --benchmark-duration 60 \
  --concurrency 100 \
  --public-dataset sharegpt
```

**That's it!** AIPerf will:
1. Create a namespace (e.g., `aiperf-20251009-143052`)
2. Deploy all required pods and services
3. Run the benchmark
4. Retrieve results to local `./artifacts/`
5. Clean up all resources

## Command-Line Options

### Kubernetes-Specific Flags

```bash
--kubernetes                              # Enable Kubernetes deployment mode
--kubernetes-namespace TEXT              # Namespace (auto-generated if not specified)
--kubernetes-image TEXT                  # Container image [default: aiperf:latest]
--kubernetes-image-pull-policy TEXT      # Pull policy [default: IfNotPresent]
--kubernetes-service-account TEXT        # Service account [default: aiperf-sa]
--kubernetes-kubeconfig PATH             # Path to kubeconfig
--kubernetes-cleanup-on-completion       # Cleanup resources after completion [default: True]

# Resource allocation
--kubernetes-worker-cpu TEXT             # CPU per worker [default: 2]
--kubernetes-worker-memory TEXT          # Memory per worker [default: 2Gi]
--kubernetes-connections-per-worker INT  # Connections per worker [default: 500]
```

### Example: High-Scale Benchmark

```bash
aiperf profile \
  --kubernetes \
  --kubernetes-namespace aiperf-production \
  --kubernetes-image aiperf:v1.0 \
  --kubernetes-worker-cpu 8 \
  --kubernetes-worker-memory 16Gi \
  --kubernetes-connections-per-worker 2000 \
  --endpoint-type chat \
  --streaming \
  -u http://your-llm-service:8000 \
  -m your-model \
  --benchmark-duration 300 \
  --concurrency 10000 \
  --public-dataset sharegpt
```

## Testing

We have comprehensive tests at multiple levels:

### Unit Tests (no cluster required)

```bash
pytest tests/test_kubernetes_components.py -v
pytest tests/test_kubernetes_implementation.py -v
```

### Integration Tests (requires cluster)

```bash
export RUN_K8S_TESTS=1
pytest tests/integration/test_kubernetes_integration.py -v
```

### End-to-End Test

```bash
./scripts/test_k8s_e2e.sh
```

See [Kubernetes Testing Guide](docs/kubernetes-testing.md) for complete details.

## Component Overview

### Kubernetes Orchestrator
- **File**: `aiperf/kubernetes/orchestrator.py`
- **Purpose**: Manages full deployment lifecycle
- **Key Methods**:
  - `deploy()`: Deploy all resources to cluster
  - `wait_for_completion()`: Monitor benchmark progress
  - `retrieve_artifacts()`: Copy results from pods to local filesystem
  - `cleanup()`: Remove all created resources

### Resource Manager
- **File**: `aiperf/kubernetes/resource_manager.py`
- **Purpose**: Low-level Kubernetes API operations
- **Key Methods**:
  - `create_namespace()`, `create_pod()`, `create_service()`
  - `wait_for_pod_ready()`: Poll pod status
  - `copy_from_pod()`: Retrieve artifacts via kubectl exec
  - `cleanup_all()`: Delete all created resources

### Pod Template Builder
- **File**: `aiperf/kubernetes/templates.py`
- **Purpose**: Generate pod/service specifications
- **Key Methods**:
  - `build_pod_spec()`: Create pod YAML for any service type
  - `build_system_controller_service()`: Create ClusterIP service
  - `build_rbac_resources()`: Generate ServiceAccount, ClusterRole, ClusterRoleBinding

### Config Serializer
- **File**: `aiperf/kubernetes/config_serializer.py`
- **Purpose**: Serialize configs for ConfigMap storage
- **Key Methods**:
  - `serialize_to_configmap()`: Convert configs → JSON strings
  - `deserialize_from_configmap()`: Restore configs from ConfigMap data

### Container Entrypoint
- **File**: `aiperf/kubernetes/entrypoint.py`
- **Purpose**: Container startup logic for all service types
- **Behavior**:
  - Reads ConfigMap to get user/service config
  - Configures ZMQ TCP endpoints based on service type
  - Bootstraps appropriate service class (Worker, SystemController, etc.)

## Configuration

### ZMQ Communication

In Kubernetes mode, AIPerf uses **ZMQ TCP** instead of IPC:

```python
# System Controller BINDS to 0.0.0.0 (all interfaces)
system_controller_service: aiperf-system-controller.{namespace}.svc.cluster.local

# Workers CONNECT to system controller via DNS
zmq_tcp.host = "aiperf-system-controller.{namespace}.svc.cluster.local"
```

### Resource Requirements

Default allocations:
- **System Controller**: 2 CPU, 2Gi memory
- **Worker**: 2 CPU, 2Gi memory (customizable via `--kubernetes-worker-cpu/memory`)
- **RecordProcessor**: 2 CPU, 2Gi memory

Adjust based on workload:
```bash
# For high-throughput benchmarks
--kubernetes-worker-cpu 8 --kubernetes-worker-memory 16Gi
```

### Namespace Management

AIPerf automatically generates unique namespaces:
```
aiperf-YYYYMMDD-HHMMSS
```

Or specify your own:
```bash
--kubernetes-namespace my-benchmark
```

**Cleanup behavior**:
- Auto-generated namespaces: Always cleaned up
- User-specified namespaces: Cleaned up if `--kubernetes-cleanup-on-completion` is True

## Advanced Usage

### Custom Docker Image

```bash
# Build with custom tag
docker build -t myregistry/aiperf:custom .

# Push to registry
docker push myregistry/aiperf:custom

# Use in benchmark
aiperf profile --kubernetes --kubernetes-image myregistry/aiperf:custom ...
```

### Using Private Image Registry

```bash
# Create secret
kubectl create secret docker-registry regcred \
  --docker-server=<your-registry> \
  --docker-username=<username> \
  --docker-password=<password>

# Update service account to use secret
# (future enhancement - currently requires manual edit of templates.py)
```

### Persistent Artifacts

To keep artifacts in cluster:

```bash
# Disable cleanup
aiperf profile \
  --kubernetes \
  --kubernetes-namespace my-benchmark \
  --kubernetes-cleanup-on-completion=false \
  ...

# Later, manually retrieve
kubectl cp my-benchmark/records-manager-0:/artifacts ./local-artifacts
```

### Multi-Cluster Deployments

```bash
# Deploy to different clusters
for cluster in prod-us-west prod-eu-central prod-ap-northeast; do
  kubectl config use-context $cluster
  aiperf profile \
    --kubernetes \
    --kubernetes-namespace aiperf-benchmark \
    --output-dir ./artifacts-$cluster \
    ...
done
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n <namespace>

# View pod logs
kubectl logs <pod-name> -n <namespace>

# Describe pod for events
kubectl describe pod <pod-name> -n <namespace>
```

### Image Pull Errors

For local clusters (minikube/kind):
```bash
# Ensure image is loaded
minikube image load aiperf:latest  # minikube
kind load docker-image aiperf:latest  # kind
```

### Permission Errors

```bash
# Verify RBAC resources
kubectl get clusterrole | grep aiperf
kubectl get clusterrolebinding | grep aiperf

# Check service account
kubectl get serviceaccount -n <namespace>
```

### Namespace Stuck in Terminating

```bash
# Force delete
kubectl patch namespace <namespace> -p '{"metadata":{"finalizers":[]}}' --type=merge
kubectl delete namespace <namespace> --grace-period=0 --force
```

### Viewing Logs

```bash
# All pods in namespace
kubectl logs -l app=aiperf -n <namespace> --all-containers=true

# Specific service type
kubectl logs -l service-type=system_controller -n <namespace>

# Follow logs
kubectl logs -f <pod-name> -n <namespace>
```

## Performance Tuning

### Scaling Workers

The number of workers is determined by `--concurrency` and `--kubernetes-connections-per-worker`:

```python
num_workers = ceil(concurrency / connections_per_worker)
```

Example:
```bash
# 10,000 concurrent connections with 2,000 connections per worker = 5 worker pods
aiperf profile \
  --kubernetes \
  --concurrency 10000 \
  --kubernetes-connections-per-worker 2000 \
  ...
```

### Network Optimization

For high-throughput benchmarks:
1. **Use faster networking**: Enable CNI plugins like Calico or Cilium
2. **Node affinity**: Schedule pods on same node to reduce latency
3. **Increase connections**: `--kubernetes-connections-per-worker 5000`

### Resource Limits

Match resources to workload:
- **CPU-bound**: Increase `--kubernetes-worker-cpu`
- **Memory-bound**: Increase `--kubernetes-worker-memory`
- **Monitor usage**: `kubectl top pods -n <namespace>`

## Files and Directories

```
aiperf/
├── kubernetes/
│   ├── __init__.py                   # Module exports
│   ├── orchestrator.py               # Main orchestration logic
│   ├── resource_manager.py           # K8s API operations
│   ├── templates.py                  # Pod/service templates
│   ├── config_serializer.py          # Config serialization
│   └── entrypoint.py                 # Container entrypoint
│
├── orchestrator/
│   ├── kubernetes_runner.py          # CLI → K8s bridge
│   └── kubernetes_cli_bridge.py      # Local CLI orchestrator
│
├── controller/
│   └── kubernetes_service_manager.py # Service manager for K8s
│
tests/
├── test_kubernetes_components.py     # Unit tests
├── test_kubernetes_implementation.py # Implementation tests
└── integration/
    ├── test_kubernetes_integration.py  # Integration tests
    └── test_kubernetes_e2e.py          # E2E tests

tools/kubernetes/
├── vllm-deployment.yaml              # vLLM test deployment
├── test-mock-server.yaml             # Simple mock server
└── mock-llm-server.yaml              # Full-featured mock LLM

scripts/
└── test_k8s_e2e.sh                   # Automated E2E test

docs/
└── kubernetes-testing.md             # Testing guide
```

## Limitations

Current limitations:
- **Single LLM endpoint**: All workers target the same endpoint URL
- **No GPU support**: GPU allocation not yet implemented
- **Manual image registry secrets**: Private registries require manual setup
- **Fixed ZMQ ports**: Port configuration is hardcoded

Future enhancements:
- GPU scheduling
- Multiple endpoint support
- HorizontalPodAutoscaler integration
- Custom resource definitions (CRDs)

## Contributing

When adding Kubernetes features:
1. **Add unit tests** to `tests/test_kubernetes_components.py`
2. **Add integration tests** to `tests/integration/test_kubernetes_integration.py`
3. **Update documentation** in this file and `docs/kubernetes-testing.md`
4. **Test on real cluster** before submitting PR

## Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)
- [Testing Guide](docs/kubernetes-testing.md)
- [AIPerf Main README](README.md)

## License

Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0

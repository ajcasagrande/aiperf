# AIPerf Kubernetes Deployment Guide

## Overview

AIPerf now supports distributed deployment on Kubernetes clusters, enabling high-concurrency load testing (100K+ concurrent connections) that exceeds single-node limitations.

## Architecture

### Component Deployment

AIPerf deploys each service as a separate Kubernetes pod:

- **System Controller Pod** (1 replica): Orchestrates benchmark lifecycle, runs ZMQ proxies
- **Dataset Manager Pod** (1 replica): Distributes conversations to workers
- **Timing Manager Pod** (1 replica): Issues request credits
- **Records Manager Pod** (1 replica): Aggregates metrics
- **Worker Manager Pod** (1 replica): Coordinates worker health
- **Worker Pods** (N replicas): Execute requests, scale based on concurrency
- **Record Processor Pods** (M replicas): Process responses and metrics

### Communication

All services communicate via ZMQ over TCP using Kubernetes DNS:
- System Controller service exposes ZMQ proxy ports (5557, 5562, 5563, 5661-5666)
- Other services connect to: `aiperf-system-controller.<namespace>.svc.cluster.local`

## Prerequisites

1. **Kubernetes Cluster**: Local (minikube, kind) or cloud (GKE, EKS, AKS)
2. **kubectl**: Configured to access your cluster
3. **Docker**: For building container images
4. **AIPerf CLI**: Installed locally

## Quick Start

### 1. Build Container Image

```bash
# Build image
docker build -t aiperf:latest -f Dockerfile.kubernetes .

# For minikube, load into cluster
minikube image load aiperf:latest

# For cloud, push to registry
docker tag aiperf:latest <your-registry>/aiperf:latest
docker push <your-registry>/aiperf:latest
```

### 2. Run Benchmark on Kubernetes

```bash
# Basic usage with auto-generated namespace
aiperf profile \
  --kubernetes \
  --kubernetes-image aiperf:latest \
  --endpoint-type chat \
  --streaming \
  -u http://my-llm-service:8080 \
  -m my-model \
  --concurrency 100000 \
  --duration 300 \
  --public-dataset sharegpt

# With custom namespace (won't auto-delete)
aiperf profile \
  --kubernetes \
  --kubernetes-namespace my-benchmark \
  --kubernetes-image aiperf:latest \
  ... # other flags
```

### 3. Results

- Artifacts are automatically retrieved to `./artifacts/`
- Metrics displayed in terminal after completion
- Namespace auto-cleaned unless `--kubernetes-namespace` specified

## Configuration Options

### Kubernetes-Specific Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--kubernetes` | Enable Kubernetes deployment | false |
| `--kubernetes-namespace` | Target namespace (auto-generated if not set) | auto |
| `--kubernetes-image` | Container image to use | aiperf:latest |
| `--kubernetes-image-pull-policy` | Image pull policy | IfNotPresent |
| `--kubeconfig` | Path to kubeconfig | ~/.kube/config |
| `--kubernetes-cleanup` | Auto-cleanup on completion | true |
| `--kubernetes-worker-cpu` | CPU per worker pod | 2 |
| `--kubernetes-worker-memory` | Memory per worker pod | 2Gi |
| `--connections-per-worker` | Connections per worker | 500 |

### Worker Scaling

AIPerf automatically calculates worker pod count:
```
num_workers = ceil(concurrency / connections_per_worker)
```

Example for 100K concurrency with 500 connections/worker = 200 worker pods

### Resource Requirements

**Minimum Cluster Resources**:
- For 10K concurrency: ~50 CPU, ~50Gi memory
- For 100K concurrency: ~500 CPU, ~500Gi memory

**Per-Pod Resources**:
- System Controller: 2 CPU, 2Gi
- Singleton services: 1 CPU, 1Gi each
- Worker pods: 2 CPU, 2Gi (configurable)
- Record processors: 2 CPU, 2Gi

## Advanced Usage

### Custom Resource Allocation

```bash
aiperf profile \
  --kubernetes \
  --kubernetes-worker-cpu "4" \
  --kubernetes-worker-memory "4Gi" \
  --connections-per-worker 1000 \
  --concurrency 200000 \
  ...
```

### Using Cloud Registry

```bash
# Push image to cloud registry
docker tag aiperf:latest gcr.io/my-project/aiperf:v1.0
docker push gcr.io/my-project/aiperf:v1.0

# Use in deployment
aiperf profile \
  --kubernetes \
  --kubernetes-image gcr.io/my-project/aiperf:v1.0 \
  --kubernetes-image-pull-policy Always \
  ...
```

### Debugging Failed Deployments

```bash
# List pods in namespace
kubectl get pods -n aiperf-<timestamp>

# Check pod logs
kubectl logs -n aiperf-<timestamp> system-controller

# Describe pod
kubectl describe pod -n aiperf-<timestamp> system-controller

# Keep resources for debugging (don't auto-delete)
aiperf profile --kubernetes --kubernetes-namespace debug-run ...
```

## Troubleshooting

### Image Pull Errors

**Problem**: `ImagePullBackOff` error

**Solutions**:
- For minikube: `minikube image load aiperf:latest`
- For cloud: Ensure image is pushed and accessible
- Check image pull policy: `--kubernetes-image-pull-policy Always`

### Pod Not Starting

**Problem**: Pod stuck in `Pending` or `CrashLoopBackOff`

**Solutions**:
```bash
# Check pod status
kubectl describe pod <pod-name> -n <namespace>

# Check logs
kubectl logs <pod-name> -n <namespace>

# Check resource availability
kubectl describe nodes
```

### RBAC Permissions

**Problem**: "Forbidden" errors during deployment

**Solution**: AIPerf automatically creates required RBAC resources. Ensure your user has cluster-admin or sufficient permissions.

### ZMQ Connection Failures

**Problem**: Services can't connect to system controller

**Solutions**:
- Verify system controller service exists: `kubectl get svc -n <namespace>`
- Check DNS resolution inside pods:
  ```bash
  kubectl exec -it <pod> -n <namespace> -- nslookup aiperf-system-controller
  ```
- Ensure ZMQ ports are exposed in service spec

## Performance Tuning

### Scaling Workers

More workers = higher concurrency, but requires more cluster resources:
- 500 connections/worker: Good balance for most cases
- 1000 connections/worker: Fewer pods, but higher per-pod load
- 250 connections/worker: More pods, better distribution

### Record Processors

Ratio: 1 record processor per 4-8 worker pods
- Adjust with `--record-processor-service-count`
- Monitor processing lag in metrics

### Dataset Distribution

For very high worker counts (500+), dataset distribution may become a bottleneck:
- Use `--public-dataset` to avoid upload
- Consider pre-caching strategies (future enhancement)

## Architecture Details

### Namespace Lifecycle

**Auto-generated namespace** (`aiperf-<timestamp>`):
- Created at deployment start
- Cleaned up after benchmark completion
- Use for temporary benchmarks

**Custom namespace**:
- Must exist or will be created
- Not auto-deleted
- Use for repeated benchmarks or debugging

### RBAC Resources

AIPerf creates:
- ServiceAccount: `aiperf-service-account`
- ClusterRole: `aiperf-role-<namespace>`
- ClusterRoleBinding: `aiperf-binding-<namespace>`

These are automatically cleaned up with the namespace.

### Configuration Distribution

Configuration is serialized to a ConfigMap and mounted into each pod:
```
ConfigMap: aiperf-config
├── user_config.json
└── service_config.json
```

### Artifact Retrieval

Results are retrieved from the Records Manager pod:
1. Benchmark completes
2. CLI copies artifacts from pod using `kubectl exec tar`
3. Files extracted to local `./artifacts/` directory
4. Pods cleaned up

## Limitations (MVP)

- No automatic pod failure recovery
- No cross-cluster deployment
- No persistent storage for artifacts
- Limited dataset pre-distribution optimization
- No real-time streaming metrics to CLI (future)

## Next Steps

- Review AIP-0002 for complete design rationale
- Test with your inference service
- Scale up gradually (10K → 50K → 100K concurrent)
- Monitor cluster resources during benchmark

## Support

For issues or questions:
- GitHub Issues: https://github.com/anthropics/aiperf/issues
- Documentation: https://docs.aiperf.nvidia.com/

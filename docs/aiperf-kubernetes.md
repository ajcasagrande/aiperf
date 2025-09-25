<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Kubernetes Deployment Enhancement

**Status**: Draft

**Authors**: @ajcasagrande

**Category**: Architecture

**Replaces**: None

**Replaced By**: None

**Sponsor**: @ganeshku

**Required Reviewers**: @ajcasagrande @ganeshku @nicolasnoble

**Review Date**: [Date for review]

**Pull Request**: [Link to Pull Request of the Proposal itself]

**Implementation PR / Tracking Issue**: [Link to Pull Request or Tracking Issue for Implementation]

# Summary

This proposal outlines the enhancement of AIPerf to support distributed deployment on Kubernetes clusters. The enhancement enables AIPerf to generate significantly higher concurrent loads by distributing work across multiple pods in a Kubernetes cluster, overcoming single-node performance limitations. The solution adopts a true per-service pod architecture where each AIPerf service runs in its own dedicated pod, enabling independent scaling and resource allocation.

AIPerf currently supports only single-node multiprocess deployment. This enhancement proposes implementing the existing `KubernetesServiceManager` stub to enable distributed deployment while maintaining full compatibility with existing service management patterns, ZMQ communication protocols, and configuration systems.

# Motivation

The current AIPerf implementation is limited to single-node execution, which constrains the maximum concurrent load that can be generated for benchmarking AI inference services. A critical limitation of single-node deployments is the exhaustion of ephemeral ports, which limits concurrent connections to approximately 65,535 per node (with practical limits around 63,500 due to reserved ports). As AI inference workloads scale to serve production traffic, there is a critical need to validate performance under extremely high concurrency conditions. Single-node AIPerf deployments cannot achieve these concurrency levels due to operating system networking constraints, hardware limitations, and the inherent scalability limits of running all services on a single machine.

Dynamo inference services are deployed on Kubernetes clusters and need to be validated against realistic, high-concurrency load patterns that exceed single-node capabilities. The lack of distributed load generation capability prevents teams from conducting comprehensive performance validation before deploying to production, potentially leading to service degradation or failures under actual concurrent user load.

## Goals

* Enable distributed load generation across multiple Kubernetes pods to achieve high concurrency levels
* Overcome single-node ephemeral port limitations by distributing connections across multiple worker pods
* Maintain compatibility with existing AIPerf CLI interfaces and configuration options
* Provide seamless deployment experience through CLI parameters and Kubernetes YAML manifests
* Preserve existing ZMQ-based communication patterns between AIPerf services while adapting for distributed deployment
* Enable scaling of worker and record processor pods based on concurrency requirements

### Non Goals

* Supporting non-Kubernetes container orchestration platforms in this implementation
* Providing a web-based UI for job management and visualization
* Implementing cross-cluster or multi-cloud distributed deployments
* Replacing the existing single-node deployment mode (both modes coexist)

## Requirements

### REQ 1 Distributed Architecture Support

AIPerf **MUST** support deployment of its services across multiple Kubernetes pods using a true per-service pod architecture while maintaining the existing service communication patterns. Each AIPerf service (system controller, dataset manager, timing manager, records manager, worker manager, worker, record processor) **MUST** run in its own dedicated pod. Worker and record processor services **MUST** be deployable as independently scalable pod replicas.

### REQ 2 Kubernetes API Integration and Compatibility

The implementation **MUST** use the Kubernetes API directly for pod orchestration rather than relying on external tools. The `KubernetesServiceManager` **MUST** implement the existing `ServiceManagerProtocol` interface to ensure compatibility with AIPerf's service management architecture. The implementation **MUST** follow the same patterns as `MultiProcessServiceManager` for service lifecycle management. The system **SHOULD** use the existing `bootstrap_and_run_service` function for service startup. The system **SHOULD** support both programmatic deployment through CLI parameters and declarative deployment through Kubernetes YAML manifests.

### REQ 3 Concurrency Scaling

The distributed deployment **MUST** be capable of sustaining at least 1M concurrent connections when deployed with sufficient pod replicas. The system **MUST** support dynamic scaling of worker pods based on target concurrency requirements and overcome single-node ephemeral port limitations.

### REQ 4 Communication Protocol Compatibility

The distributed implementation **MUST** maintain compatibility with existing ZMQ-based communication patterns. All inter-service communication **MUST** function correctly across pod boundaries using the same message protocols.

### REQ 5 Deployment Lifecycle Management

The system **MUST** support complete lifecycle management including deployment, configuration, execution, and cleanup of Kubernetes resources. Failed deployments **SHOULD** be automatically cleaned up to prevent resource leaks.

### REQ 6 Developer Experience and Simplicity

The implementation **MUST** provide a simple, intuitive deployment experience that allows developers to achieve 1M+ concurrent connections with minimal configuration. The system **SHOULD** follow basic Kubernetes security practices while prioritizing ease of use and performance over enterprise complexity.


# Proposal

## Architecture Overview

The proposed Kubernetes deployment architecture adopts a true per-service pod approach where each AIPerf service runs in its own dedicated pod. This design provides maximum flexibility for independent scaling, resource allocation, and fault isolation. The architecture separates AIPerf services into two categories:

1. **Singleton Service Pods**: Core coordination services that run as single instances
2. **Scalable Service Pods**: Services that scale horizontally based on load requirements

### Service Pod Architecture

#### System Controller Pod
- **Single pod** running the system controller service
- Orchestrates the entire benchmark lifecycle and coordinates other services
- Manages the ProxyManager with embedded ZMQ proxies for message routing
- Singleton deployment - only one instance per benchmark

#### Dataset Manager Pod
- **Single pod** running the dataset manager service
- Manages dataset loading and distribution across the cluster
- Singleton deployment - only one instance per benchmark

#### Timing Manager Pod
- **Single pod** running the timing manager service
- Issues credits (request tokens) and controls benchmark timing
- Singleton deployment - only one instance per benchmark

#### Records Manager Pod
- **Single pod** running the records manager service
- Collects and aggregates metrics from distributed record processors
- Singleton deployment - only one instance per benchmark

#### Worker Manager Pod
- **Single pod** running the worker manager service
- Coordinates worker scaling and management operations
- Singleton deployment - only one instance per benchmark

#### Worker Pods (Scalable)
- **Multiple pods** each running a single worker service instance
- Execute inference requests against target endpoints
- Scale horizontally based on target concurrency requirements (1 to N replicas)
- Each pod can handle concurrent connections up to the configured `AIPERF_HTTP_CONNECTION_LIMIT`

#### Record Processor Pods (Scalable)
- **Multiple pods** each running a single record processor service instance
- Perform request and response tokenization and initial metrics processing
- Scale horizontally based on response processing throughput and concurrent request volume (1 to N replicas)
- Send processed metrics back to the records manager via ZMQ

## Communication Architecture

The existing ZMQ-based communication patterns are preserved with the following adaptations for distributed deployment:

### ZMQ Communication Flow
The existing ZMQ communication uses multiple proxy patterns managed by the ProxyManager:

1. **Credit Distribution**: Timing manager pushes credits through CREDIT_DROP address, workers pull via PUSH/PULL pattern
2. **Credit Return**: Workers return completed credits through CREDIT_RETURN address
3. **Raw Inference Results**: Workers send raw responses through RAW_INFERENCE_PROXY_FRONTEND to record processors via PUSH/PULL proxy
4. **Processed Records**: Record processors send processed metrics to records manager via RECORDS address using PUSH/PULL
5. **Event Bus**: System controller and services communicate via EVENT_BUS_PROXY using PUB/SUB pattern for coordination messages
6. **Dataset Requests**: Workers request conversation data from dataset manager via DATASET_MANAGER_PROXY using DEALER/ROUTER pattern

### Network Configuration
- System controller pod exposes ZMQ proxy ports via Kubernetes services
- All service pods connect to system controller services using Kubernetes DNS
- Each singleton service pod exposes its own service endpoint for direct communication
- All ZMQ communication uses TCP transport with connection pooling and keep-alive optimization
- Network policies enforce service isolation and security boundaries
- Support for high-performance networking (SR-IOV, DPDK) in HPC environments

## Deployment Modes

### CLI-Driven Deployment

**Kubernetes Deployment** (Simple):
```bash
# Easy deployment for 1M+ concurrency
aiperf profile \
       --service-run-type k8s \
       --concurrency 1000000 \
       --target-url http://inference-service:8080

# Advanced deployment with custom scaling
aiperf profile \
       --service-run-type k8s \
       --concurrency 1000000 \
       --worker-replicas 20 \
       --target-url http://inference-service:8080 \
       --namespace my-load-test
```

**Multiprocess Deployment** (current default):
```bash
aiperf profile \
       --workers-max 50 \
       --record-processor-service-count 10 \
       --target-url http://inference-service:8080 \
       --log-level debug
```

### Auto-Scaling for Massive Concurrency
AIPerf automatically calculates optimal pod distribution for target concurrency:

```bash
# AIPerf automatically scales to achieve 1M+ concurrent connections
aiperf profile \
       --service-run-type k8s \
       --concurrency 1500000 \
       --url http://my-llm-service:8080 \
       --duration 300s

# AIPerf calculates:
# - Worker pods needed based on connection limits
# - Record processor scaling based on throughput
# - Resource allocation for optimal performance
```

**Example Auto-Scaling Logic**:
- Target: 1,500,000 concurrent connections
- Connection limit per worker pod: 50,000 (validated from `AIPERF_HTTP_CONNECTION_LIMIT`)
- Required worker pods: 30 (with 20% buffer)
- Record processors: 8 (auto-scaled based on worker count)
- Total deployment: 39 pods across 7 service types

## Resource Management

### Simple Resource Allocation
AIPerf uses sensible defaults optimized for performance:

**Default Resource Allocation** (Auto-tuned for scale):
- **Control Services** (system-controller, dataset-manager, etc.): 1 CPU, 2Gi memory each
- **Worker Pods**: 2 CPU, 4Gi memory (optimized for high concurrency)
- **Record Processors**: 1 CPU, 2Gi memory (auto-scaled with workload)

**Custom Resource Tuning** (Optional):
```bash
# Customize resources for specific environments
aiperf profile \
       --service-run-type k8s \
       --concurrency 1000000 \
       --worker-cpu 4 \
       --worker-memory 8Gi \
       --target-url http://inference-service:8080
```

**Performance-First Defaults**:
- Minimal resource overhead for control services
- Auto-scaling based on actual workload demand

### Scaling Strategy
- Singleton service pods (system controller, dataset manager, timing manager, records manager, worker manager) remain single instances
- Worker pods scale linearly with target concurrency requirements (1 to N replicas)
- Each worker pod can sustain concurrent connections up to the configured `AIPERF_HTTP_CONNECTION_LIMIT` before connection exhaustion
- For 100,000+ concurrent connections, deploy multiple worker pods to distribute the connection load based on validated `AIPERF_HTTP_CONNECTION_LIMIT`
- Record processor pods scale based on response processing throughput using HPA with custom metrics (processing queue depth, CPU utilization)
- Each service can be independently configured with specific resource limits and requests
- Integration with Cluster Autoscaler for node-level scaling in cloud environments
- Support for GPU resource allocation for ML-based tokenization and processing workloads

# Implementation Details

## Kubernetes Service Manager

The `KubernetesServiceManager` class implements the existing `ServiceManagerProtocol` interface to handle Kubernetes-specific deployment logic, following the same patterns as `MultiProcessServiceManager`:

### ServiceManagerProtocol Implementation
The `KubernetesServiceManager` extends `BaseServiceManager` and implements all required protocol methods:
- `run_service(service_type, num_replicas)`: Deploy individual service pods using Kubernetes API, similar to how `MultiProcessServiceManager.run_service()` spawns processes
- `shutdown_all_services()`: Clean up all deployed Kubernetes resources, similar to multiprocess termination
- `kill_all_services()`: Force kill all pods, similar to `process.kill()` in multiprocess manager
- `wait_for_all_services_registration()`: Monitor pod readiness and service registration using the same service registry pattern
- `wait_for_all_services_start()`: Wait for pod startup (currently not implemented in multiprocess manager)

**Critical Integration Note**: The existing `WorkerManager` service handles worker lifecycle management with CPU-based scaling logic. The Kubernetes implementation must decide whether to:
1. Preserve `WorkerManager` and have it coordinate with Kubernetes scaling
2. Replace `WorkerManager` functionality with native Kubernetes scaling (HPA/VPA)
3. Hybrid approach where `WorkerManager` acts as a Kubernetes controller

### Core Components
- **Pod Template Generation**: Creates Kubernetes pod specifications for each individual service type
- **Service Discovery**: Manages Kubernetes services for ZMQ communication endpoints between service pods
- **Resource Lifecycle**: Handles deployment, scaling, and cleanup of individual service pod resources
- **Health Monitoring**: Monitors individual service pod health and handles failures/restarts
- **RBAC Management**: Programmatically creates and manages RBAC permissions for AIPerf operations

### API Integration
```python
@implements_protocol(ServiceManagerProtocol)
@ServiceManagerFactory.register(ServiceRunType.KUBERNETES)
class KubernetesServiceManager(BaseServiceManager):
    def __init__(self,
                 required_services: dict[ServiceTypeT, int],
                 service_config: ServiceConfig,
                 user_config: UserConfig,
                 log_queue: "multiprocessing.Queue | None" = None,  # Maintains compatibility
                 **kwargs):
        super().__init__(required_services, service_config, user_config, **kwargs)
        self.k8s_client = kubernetes.client.ApiClient()
        self.apps_v1 = kubernetes.client.AppsV1Api(self.k8s_client)
        self.core_v1 = kubernetes.client.CoreV1Api(self.k8s_client)
        self.rbac_v1 = kubernetes.client.RbacAuthorizationV1Api(self.k8s_client)
        self.kubernetes_run_info: list[ServiceKubernetesRunInfo] = []  # Parallel to MultiProcessRunInfo

    async def run_service(self, service_type: ServiceTypeT, num_replicas: int = 1) -> None:
        """Deploy service pods, similar to MultiProcessServiceManager.run_service()"""
        service_class = ServiceFactory.get_class_from_type(service_type)

        for _ in range(num_replicas):
            service_id = f"{service_type}_{uuid.uuid4().hex[:8]}"
            # Deploy pod using Kubernetes API instead of Process()
            # Store pod info in kubernetes_run_info similar to multi_process_info

    async def _setup_rbac_resources(self) -> None:
        # Create ServiceAccount, ClusterRole, and ClusterRoleBinding

    async def _cleanup_rbac_resources(self) -> None:
        # Remove RBAC resources when benchmark completes
```

## ZMQ Network Configuration

### Service Exposure
The system controller pod exposes ZMQ proxy endpoints via Kubernetes services, while other services connect as clients:
```yaml
# System Controller Service (ZMQ Proxies)
apiVersion: v1
kind: Service
metadata:
  name: aiperf-system-controller
spec:
  selector:
    app: aiperf-system-controller
  ports:
    # Credit distribution (timing manager pushes, workers pull)
    - name: credit-drop
      port: 5562
      targetPort: 5562
    # Credit return (workers push back completed credits)
    - name: credit-return
      port: 5563
      targetPort: 5563
    # Raw inference proxy frontend (workers push responses)
    - name: raw-inference-proxy-frontend
      port: 5665
      targetPort: 5665
    # Records collection (record processors push processed data)
    - name: records
      port: 5557
      targetPort: 5557
    # Event bus proxy frontend (PUB/SUB for coordination)
    - name: event-bus-proxy-frontend
      port: 5663
      targetPort: 5663
    # Dataset manager proxy frontend (workers request data)
    - name: dataset-manager-proxy-frontend
      port: 5661
      targetPort: 5661
```

### Connection Configuration
Service pods use Kubernetes DNS for service discovery to connect to system controller proxies:
```python
# Service discovery configuration for accessing ZMQ proxies
SYSTEM_CONTROLLER_SERVICE = "aiperf-system-controller.aiperf-benchmarks.svc.cluster.local"

# ZMQ endpoint configuration using actual CommAddress mappings
CREDIT_DROP_ENDPOINT = f"tcp://{SYSTEM_CONTROLLER_SERVICE}:5562"
CREDIT_RETURN_ENDPOINT = f"tcp://{SYSTEM_CONTROLLER_SERVICE}:5563"
RAW_INFERENCE_PROXY_FRONTEND = f"tcp://{SYSTEM_CONTROLLER_SERVICE}:5665"
RECORDS_ENDPOINT = f"tcp://{SYSTEM_CONTROLLER_SERVICE}:5557"
EVENT_BUS_PROXY_FRONTEND = f"tcp://{SYSTEM_CONTROLLER_SERVICE}:5663"
DATASET_MANAGER_PROXY_FRONTEND = f"tcp://{SYSTEM_CONTROLLER_SERVICE}:5661"

# Services connect as clients to these proxy endpoints
# Workers: connect to CREDIT_DROP (pull), CREDIT_RETURN (push), RAW_INFERENCE_PROXY_FRONTEND (push)
# Record Processors: connect to RAW_INFERENCE_PROXY_BACKEND (pull), RECORDS (push)
# All Services: connect to EVENT_BUS_PROXY (pub/sub for coordination)
```

## CLI App Responsibilities

### RBAC and Resource Management
The AIPerf CLI app is responsible for creating and managing all necessary Kubernetes resources programmatically through the Kubernetes API:

#### RBAC Resource Creation
```python
# ServiceAccount for AIPerf operations
service_account = {
    "apiVersion": "v1",
    "kind": "ServiceAccount",
    "metadata": {
        "name": "aiperf-service-account",
        "namespace": namespace
    }
}

# ClusterRole with required permissions (following least-privilege principle)
cluster_role = {
    "apiVersion": "rbac.authorization.k8s.io/v1",
    "kind": "ClusterRole",
    "metadata": {"name": "aiperf-cluster-role"},
    "rules": [
        {
            "apiGroups": [""],
            "resources": ["pods", "services", "configmaps"],
            "verbs": ["create", "get", "list", "watch", "update", "patch", "delete"]
        },
        {
            "apiGroups": ["apps"],
            "resources": ["deployments", "replicasets"],
            "verbs": ["create", "get", "list", "watch", "update", "patch", "delete"]
        },
        {
            "apiGroups": ["autoscaling"],
            "resources": ["horizontalpodautoscalers"],
            "verbs": ["create", "get", "list", "watch", "update", "patch", "delete"]
        }
    ]
}

# ClusterRoleBinding to associate ServiceAccount with ClusterRole
cluster_role_binding = {
    "apiVersion": "rbac.authorization.k8s.io/v1",
    "kind": "ClusterRoleBinding",
    "metadata": {"name": "aiperf-cluster-role-binding"},
    "subjects": [{"kind": "ServiceAccount", "name": "aiperf-service-account", "namespace": namespace}],
    "roleRef": {"kind": "ClusterRole", "name": "aiperf-cluster-role", "apiGroup": "rbac.authorization.k8s.io"}
}
```

#### Direct API vs YAML File Usage
The CLI app **MUST** use the Kubernetes Python client to create resources programmatically rather than generating YAML files:

**Preferred Approach (Direct API):**
```python
# Create resources directly through API
await self.core_v1.create_namespaced_service_account(namespace, service_account)
await self.rbac_v1.create_cluster_role(cluster_role)
await self.rbac_v1.create_cluster_role_binding(cluster_role_binding)
```

**Alternative Approach (YAML files - only for user reference):**
- YAML manifests **MAY** be generated for user inspection or manual deployment scenarios
- Generated YAML files **SHOULD** be stored in temporary directories and cleaned up after use
- Direct API usage provides better error handling and programmatic resource lifecycle management

#### Resource Lifecycle Management
```python
class KubernetesResourceManager:
    async def setup_benchmark_resources(self) -> None:
        """Create all necessary RBAC and service resources for benchmark execution"""
        await self._create_namespace_if_not_exists()
        await self._setup_rbac_resources()
        await self._create_config_maps()

    async def cleanup_benchmark_resources(self) -> None:
        """Remove all created resources after benchmark completion"""
        await self._cleanup_services()
        await self._cleanup_deployments()
        await self._cleanup_rbac_resources()
        await self._cleanup_config_maps()
```

## Configuration Management

### CLI Parameters

**Current Implementation**: The `service_run_type` parameter is currently disabled in CLI via `DisableCLI(reason="Only single support for now")` and defaults to `ServiceRunType.MULTIPROCESSING`. Kubernetes support requires removing the `DisableCLI` decorator and enabling this parameter with proper CLI integration.

**Kubernetes Deployment Parameters**:
- `--service-run-type k8s`: Enable Kubernetes deployment mode
- `--kubernetes-namespace`: Target Kubernetes namespace
- `--kubeconfig`: Path to Kubernetes configuration file

**Existing Parameters (Work with Both Deployment Modes)**:
- `--record-processor-service-count`: Controls record processor scaling
- `--workers-max` / `--max-workers`: Controls worker scaling
- `--log-level`, `--verbose`, `--extra-verbose`: Service logging configuration
- `--ui-type` / `--ui`: UI configuration

### Environment Variable Injection
Configuration is passed to pods via environment variables and ConfigMaps:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: aiperf-config
data:
  target_url: "http://inference-service:8080"
  benchmark_duration: "300"
  # ... other AIPerf configuration
```

## Basic Security

AIPerf follows basic Kubernetes security practices without unnecessary complexity:

### Simple RBAC
```yaml
# Basic permissions for AIPerf operations
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: aiperf-operator
rules:
- apiGroups: [""]
  resources: ["pods", "services", "configmaps"]
  verbs: ["create", "get", "list", "watch", "delete"]
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["create", "get", "list", "watch", "delete"]
```

### Pod Security (Basic)
```yaml
# Simple non-root execution
apiVersion: v1
kind: Pod
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
  containers:
  - name: aiperf-worker
    securityContext:
      allowPrivilegeEscalation: false
```

**Security Philosophy**:
- Keep it simple and functional
- Basic non-root execution
- Standard Kubernetes RBAC
- No complex network policies by default
- Focus on performance over paranoid security

## Performance for 1M+ Concurrency

### Connection Scaling (The Key Challenge)
Getting to 1M+ concurrent connections requires smart pod distribution:

```python
# Simple scaling calculation built into AIPerf
def calculate_worker_pods(target_concurrency: int) -> int:
    """Auto-calculate worker pods needed for target concurrency."""
    connections_per_pod = get_connection_limit()  # From AIPERF_HTTP_CONNECTION_LIMIT
    safety_buffer = 0.8  # 20% buffer for stability
    effective_limit = int(connections_per_pod * safety_buffer)
    return math.ceil(target_concurrency / effective_limit)

# Example: 1M target with 50K limit = 25 worker pods
```

### ZMQ Performance Optimization
Simple optimizations for maximum throughput:

```yaml
# Built-in performance tuning
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: aiperf-worker
    env:
    - name: ZMQ_MAX_SOCKETS
      value: "65536"
    - name: ZMQ_IO_THREADS
      value: "4"
    resources:
      requests:
        cpu: 2
        memory: 4Gi
```

### Network Performance
- **DNS Caching**: Built-in service discovery optimization
- **Connection Pooling**: ZMQ connection reuse and keep-alive
- **Buffer Optimization**: Auto-tuned for high concurrency workloads

**Performance Targets**:
- 1M+ concurrent connections across distributed worker pods
- <5ms additional latency vs single-node deployment
- Linear scaling with pod count (no bottlenecks)

## Container Images

### Container Image
A single container image supports all AIPerf service modes with performance optimizations:
```dockerfile
FROM python:3.11-slim

# Install performance monitoring tools
RUN apt-get update && apt-get install -y \
    htop iotop tcpdump strace \
    && rm -rf /var/lib/apt/lists/*

# Optimize Python for container environments
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONHASHSEED=random

# ZMQ performance tuning
ENV ZMQ_MAX_SOCKETS=65536
ENV ZMQ_IO_THREADS=4

COPY aiperf/ /app/aiperf/
WORKDIR /app
ENTRYPOINT ["python", "-m", "aiperf.kubernetes_runner"]
```

### Service Mode Selection
Service mode is determined by environment variables, leveraging the existing `ServiceFactory`:
```python
# kubernetes_runner.py
import os
from aiperf.common.bootstrap import bootstrap_and_run_service
from aiperf.common.factories import ServiceFactory
from aiperf.common.enums import ServiceType

service_type_str = os.getenv("AIPERF_SERVICE_TYPE")
service_type = ServiceType(service_type_str)
service_class = ServiceFactory.get_class_from_type(service_type)

bootstrap_and_run_service(
    service_class=service_class,
    service_config=load_service_config(),
    user_config=load_user_config(),
    service_id=os.getenv("AIPERF_SERVICE_ID"),
)
```

## Simple Monitoring

AIPerf provides built-in monitoring that works out of the box:

### Real-time Performance Metrics
```bash
# Built-in monitoring during test execution
aiperf profile \
       --service-run-type k8s \
       --concurrency 1000000 \
       --target-url http://inference-service:8080 \
       --monitor

# Live output shows:
# ✓ Worker pods: 20/20 ready
# ✓ Concurrent connections: 987,234 / 1,000,000
# ✓ Request rate: 45,678 req/s
# ✓ P95 latency: 123ms
# ✓ Error rate: 0.02%
```

### Basic Health Checks
```yaml
# Simple health monitoring
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: aiperf-worker
    livenessProbe:
      httpGet:
        path: /health
        port: 8080
      initialDelaySeconds: 10
      periodSeconds: 30
    readinessProbe:
      httpGet:
        path: /ready
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 10
```

### **Deferred to Implementation**
- **Optimal ZMQ port allocation strategy**: Determine whether to use fixed ports or dynamic port allocation with service discovery
- **Pod anti-affinity rules**: Decide on pod placement strategies to optimize network performance and resource distribution
- **Persistent volume integration**: Define strategy for sharing dataset files and result artifacts across pods
- **Custom Resource Definition (CRD)**: Evaluate whether to implement a native Kubernetes CRD for BenchmarkJob resources
- **Graceful shutdown handling**: Implementation details for clean termination of distributed benchmark runs
- **Metric aggregation optimization**: Determine optimal batching and streaming strategies for high-volume metrics collection
- **ConfigMap vs Secret usage**: Define strategy for sensitive configuration data (API keys, certificates) vs regular config

# Implementation Phases

## Phase 0 Kubernetes Integration (MVP)

**Release Target**: Q1 2026

**Effort Estimate**: 6-8 weeks, 2 engineers

**Focus**: Get 1M+ concurrency working with simple, reliable deployment

**Core Features:**

* ✅ CLI deployment: `aiperf profile --service-run-type k8s --concurrency 1000000`
* ✅ Auto-scaling worker pods based on concurrency target
* ✅ ZMQ communication across pod boundaries
* ✅ Built-in monitoring and health checks
* ✅ Automatic cleanup after test completion
* ✅ Basic security (non-root, simple RBAC)

# Related Proposals

N/A - This is the initial proposal for Kubernetes deployment support in AIPerf.

# Alternate Solutions

## Alt 1 Single Monolithic Pod Deployment

**Pros:**

* Simpler deployment model with fewer moving parts
* Easier debugging and troubleshooting with all services in one place
* Reduced network complexity as all communication remains local
* Lower resource overhead from avoiding inter-pod communication

**Cons:**

* Limited scalability as all services share the same resource constraints
* Difficult to scale individual services (workers, record processors) independently
* Higher memory usage per pod due to co-location of all services
* Reduced fault tolerance as single pod failure affects entire benchmark

**Reason Rejected:**

* Does not address the core requirement of generating high concurrency loads beyond single-node limits
* Cannot overcome connection limitations imposed by `AIPERF_HTTP_CONNECTION_LIMIT` configuration
* Prevents independent scaling of worker services which is essential for distributed load generation
* Conflicts with the architectural decision to adopt true per-service pod architecture for maximum flexibility

**Notes:**

This approach is similar to the current single-node deployment but containerized for Kubernetes. While simpler, it fails to leverage the primary benefits of distributed deployment.

## Alt 2 Hybrid Co-location Approach

**Pros:**

* Reduces pod count by co-locating coordination services
* Simpler service discovery with fewer network endpoints
* Potentially lower networking overhead between co-located services
* Easier resource management for singleton services

**Cons:**

* Mixed approach complicates deployment logic (some services co-located, others separate)
* Less flexibility for independent resource tuning of singleton services
* Reduced fault tolerance as controller pod failure affects multiple services
* Harder to debug individual service issues when co-located

**Reason Rejected:**

* Per-service pods provide maximum flexibility and isolation
* Resource requirements for singleton services are sufficiently small that co-location benefits are minimal
* Consistency of having all services in individual pods simplifies architecture

## Alt 3 Kubernetes Job-Based Deployment Only

**Pros:**

* Leverages native Kubernetes job scheduling and lifecycle management
* Integrates well with CI/CD pipelines and batch processing workflows
* Automatic cleanup and resource management through Kubernetes job controller
* Simple YAML-based configuration without custom CLI extensions

**Cons:**

* Limited real-time control and monitoring during benchmark execution
* Difficult to implement dynamic scaling based on runtime metrics
* Reduced flexibility for interactive benchmark sessions
* May not support complex coordination patterns required by AIPerf

**Reason Rejected:**

* Meeting discussion indicated desire for both interactive CLI-driven deployment and job-based execution
* Constraints of Kubernetes job model may limit AIPerf's coordination capabilities
* Decision made to support CLI-driven deployment as primary interface

**Notes:**

Job-based deployment provides excellent CI/CD integration but limits real-time interaction capabilities.

## Alt 4 External Orchestrator with Helm Charts

**Pros:**

* Leverages mature Helm ecosystem for templating and package management
* Easier deployment across different Kubernetes distributions
* Built-in versioning and rollback capabilities through Helm
* Community-standard approach for complex Kubernetes applications

**Cons:**

* Adds external dependency on Helm installation and management
* More complex CLI implementation to generate and apply Helm charts
* Additional learning curve for users unfamiliar with Helm
* May complicate custom resource management and cleanup logic

**Reason Rejected:**

* Meeting emphasized using Kubernetes API directly rather than external tools
* Adds complexity without addressing core scaling requirements
* Direct API approach provides more control over resource lifecycle management

**Notes:**

Helm charts could be provided as an optional deployment method in future releases.

# Background

AIPerf is NVIDIA's AI inference performance benchmarking tool designed to validate and stress-test AI inference services. The current implementation uses a multi-service architecture where services communicate via ZeroMQ (ZMQ) message passing. Services include the system controller (orchestration), dataset manager (data loading), timing manager (request rate control), workers (request execution), and record processors (response processing and metrics).

The single-node limitation has become a significant constraint as AI inference workloads scale to production-level concurrency volumes. A fundamental bottleneck is the exhaustion of ephemeral ports on a single system, which limits concurrent TCP connections to approximately 65,535 ports per node (practical limit ~63,500). Modern AI inference services require validation against concurrent loads exceeding 100,000 simultaneous connections, particularly for large language models and computer vision services deployed in production environments.

## References

* [Kubernetes API Documentation](https://kubernetes.io/docs/reference/kubernetes-api/)
* [ZeroMQ Distributed Messaging Guide](https://zguide.zeromq.org/docs/chapter4/)
* [Kubernetes Deployment and ReplicaSet Concepts](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)

## Terminology & Definitions

| Term | Definition |
| :---- | :---- |
| **Credit** | Token representing a single inference request to be executed by a worker |
| **Ephemeral Port** | Temporary port assigned by the OS for outbound connections, limited to ~65,535 per node |
| **Per-Service Pod** | Architecture where each AIPerf service runs in its own dedicated Kubernetes pod |
| **Record Processor** | AIPerf service responsible for response tokenization and initial metrics processing |
| **Service Pod** | Kubernetes pod containing a single AIPerf service instance |
| **ZMQ Proxy** | Service that routes messages between distributed ZeroMQ clients using various patterns |

## Acronyms & Abbreviations

**CRD:** Custom Resource Definition
**HPA:** Horizontal Pod Autoscaler
**mTLS:** Mutual Transport Layer Security
**NUMA:** Non-Uniform Memory Access
**RBAC:** Role-Based Access Control
**SR-IOV:** Single Root I/O Virtualization
**VPA:** Vertical Pod Autoscaler
**ZMQ:** ZeroMQ
